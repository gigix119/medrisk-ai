# Faza 3: API inferencji histopatologicznej — przewodnik edukacyjny

Ten dokument zakłada znajomość Fazy 1 (FastAPI, warstwy `api`/`services`/`repositories`, SQLAlchemy async) i Fazy 2 (PyTorch, model binarny, checkpoint, bundle, Grad-CAM) — patrz [phase-01-backend-foundation.md](phase-01-backend-foundation.md) i [phase-02-histopathology-ml.md](phase-02-histopathology-ml.md). Faza 3 nie powtarza tamtej teorii — skupia się wyłącznie na tym, co jest nowe, gdy gotowy model trzeba uruchomić *za prawdziwym, współbieżnym, publicznym API*, a nie w skrypcie treningowym.

> Ten sam disclaimer co w Fazie 2 obowiązuje tu w pełni — i dotyczy teraz też samego API, nie tylko skryptu: *"This software is an educational and research portfolio project. It is not a medical device and must not be used for diagnosis, treatment decisions, or emergency medical guidance."*

---

## 1. Od artefaktu do API — co właściwie znaczy "wiring"

Faza 2 zostawiła folder na dysku: wagi, manifest, próg, kalibrację, model_card — kompletny, samowystarczalny "bundle". Faza 3 to wyłącznie odpowiedź na pytanie "jak ten folder zamienia się w odpowiedź HTTP", bez zmiany ani jednej linii w `medrisk_ml/`.

**Gdzie w repo**: nowy pakiet `medrisk_inference/` — `bundle.py` (wczytaj+zweryfikuj folder), `runtime.py` (zbuduj model z wczytanych danych), `service.py` (połącz walidację obrazu z predykcją). Żaden z tych plików nie importuje `app.*`; tylko `app/services/model_deployment.py` i `app/services/prediction.py` importują `medrisk_inference`.

```python
# medrisk_inference/bundle.py
def load_bundle(bundle_path: str | Path, config: InferenceConfig) -> LoadedBundle:
    ...
    result = verify_bundle(bundle_dir)  # medrisk_ml's own checksum + smoke-inference check
    if not result.valid:
        raise BundleInvalidError(f"Model bundle failed verification: {'; '.join(result.errors)}")
```

**Częsty błąd początkującego**: traktowanie "wirowania" jako kopiowania kodu treningowego do API. Tu dzieje się odwrotnie — `medrisk_inference` woła z `medrisk_ml` tylko to, co jest *bezpieczne dla produkcji* (`registry.bundle`, `models.factory`, `data.transforms`, `explainability.gradcam`) i nigdy `training/`, `data.datasets` (prawdziwy PCam), czy `cli.py`.

**Pytanie rekrutacyjne**: Czemu `medrisk_inference` nie mógłby po prostu zaimportować `medrisk_ml.cli` i wywołać tam zdefiniowanej funkcji `predict`, gdyby taka istniała?

---

## 2. FastAPI `lifespan` i `app.state`

Faza 1 nie potrzebowała żadnego stanu współdzielonego między żądaniami poza silnikiem bazy danych (który i tak żyje poza `app.state`, jako moduł-level singleton). Model PyTorch jest inny: jego wczytanie jest kosztowne (sekundy), więc musi się wydarzyć **raz, przy starcie procesu**, a wynik musi być dostępny dla *każdego* żądania bez ponownego wczytywania.

**Gdzie w repo**: `app/main.py::lifespan` — async context manager opakowujący cały czas życia aplikacji; kod przed `yield` to startup, kod po `yield` to shutdown.

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.histopathology_model = None
    app.state.inference_semaphore = asyncio.Semaphore(max(1, settings.INFERENCE_MAX_CONCURRENCY))
    async with AsyncSessionLocal() as session:
        app.state.histopathology_model = await initialize_histopathology_deployment(session, settings)
    yield
    if app.state.histopathology_model is not None:
        app.state.histopathology_model.runtime.close()
    await engine.dispose()
```

**Częsty błąd początkującego**: wczytywanie modelu *wewnątrz* funkcji endpointu ("na wszelki przypadek, gdyby `app.state` było puste"). To dokładnie odtwarza problem, który `lifespan` ma rozwiązać — model wczytywałby się przy pierwszym żądaniu (albo, gorzej, przy każdym).

**Pytanie rekrutacyjne**: Co konkretnie się stanie, jeśli kod po `yield` w `lifespan` rzuci wyjątek — czy klient w trakcie obsługiwanego żądania to zobaczy?

---

## 3. Runtime jako singleton procesu ("load once, serve many")

`HistopathologyModelRuntime` to jeden obiekt, budowany raz, przechowujący model, urządzenie, transformację, kalibrację, próg i politykę przeglądu (`review_policy`) — wszystko, co potrzebne, by obsłużyć predykcję, bez ponownego czytania bundla z dysku.

**Gdzie w repo**: `medrisk_inference/runtime.py::HistopathologyModelRuntime.from_bundle` — klasowa metoda fabrykująca, wołana raz w `initialize_histopathology_deployment`.

```python
class HistopathologyModelRuntime:
    def __init__(self, *, model, manifest, device, transform, calibration, bundle_sha256, config):
        self.model = model
        self.threshold = manifest.threshold
        self.review_policy = parse_review_policy(manifest.review_policy)
        ...
```

**Częsty błąd początkującego**: budowanie nowego `HistopathologyModelRuntime` (albo nawet tylko nowego `torch.nn.Module` + `load_state_dict`) wewnątrz funkcji obsługującej żądanie. To działałoby funkcjonalnie, ale zamieniałoby każde żądanie w mini-restart — sekundy zamiast milisekund, i to przy każdym requeście.

**Pytanie rekrutacyjne**: Endpoint inferencji jest wołany współbieżnie przez 5 żądań naraz. Ile obiektów `HistopathologyModelRuntime` istnieje w pamięci procesu w tym momencie?

---

## 4. `MODEL_REQUIRED` — fail-fast kontra graceful degradation

To samo zdarzenie (bundle się nie wczytuje) ma dwie zupełnie różne, jawnie skonfigurowane reakcje, zależnie od środowiska.

**Gdzie w repo**: `app/services/model_deployment.py::initialize_histopathology_deployment` — jedna funkcja, dwie ścieżki.

```python
except InferenceError as exc:
    if settings.MODEL_REQUIRED:
        raise ModelStartupError(str(exc)) from exc  # proces NIE wstaje
    return None  # proces wstaje, endpointy odpowiadają 503
```

**Częsty błąd początkującego**: zakładanie, że "bezpieczniej" jest zawsze wystartować aplikację, nawet bez modelu — "przynajmniej health-check będzie działał". To dobre dla środowiska deweloperskiego (możesz pracować nad resztą API bez modelu pod ręką), ale fatalne dla produkcji — `Settings.validate_production_model_policy` dlatego *wymusza* `MODEL_REQUIRED=true` w `ENVIRONMENT=production`, zamiast pozwolić na cichy, działający-ale-bezużyteczny serwer.

**Pytanie rekrutacyjne**: Czemu walidacja `MODEL_REQUIRED=true` w produkcji jest zaimplementowana jako `@model_validator` w `Settings` (Pydantic), a nie jako `if` na początku `initialize_histopathology_deployment`?

---

## 5. Ścieżka modelu nigdy z żądania + `weights_only=True`

Dwie niezależne decyzje, które razem eliminują całą klasę podatności związanych z deserializacją i odczytem arbitralnych plików.

**Gdzie w repo**: `MODEL_BUNDLE_PATH` to zmienna środowiskowa czytana raz przy starcie (`InferenceConfig.model_bundle_path`) — żaden parametr żądania, żaden upload nie staje się ścieżką do modelu. `medrisk_inference/runtime.py::from_bundle`:

```python
state_dict = torch.load(bundle.bundle_dir / "model_state.pt", map_location="cpu", weights_only=True)
```

**Częsty błąd początkującego**: traktowanie `weights_only=True` jako "opcji wydajności" do ewentualnego wyłączenia, gdy coś nie działa. To w rzeczywistości ograniczenie bezpieczeństwa — pełne (nie-`weights_only`) odpicklowanie w PyTorch potrafi wykonać dowolny kod zapisany w pliku; `weights_only=True` ogranicza unpickler do tensorów i prostych typów.

**Pytanie rekrutacyjne**: Gdyby ten projekt pozwolił API-użytkownikowi przekazać `model_bundle_path` jako parametr żądania "dla wygody testowania" — jakie konkretnie nowe wektory ataku by to otworzyło, niezależnie od `weights_only=True`?

---

## 6. Multipart upload w FastAPI — `UploadFile`, `File`, `Form`

Obraz i metadane (`include_explanation`, `client_reference`) przychodzą w jednym żądaniu `multipart/form-data`, nie w JSON — to, w odróżnieniu od reszty API z Fazy 1, jedyny endpoint, który nie jest czystym JSON-em.

**Gdzie w repo**: `app/api/v1/endpoints/predictions.py::predict_histopathology`.

```python
async def predict_histopathology(
    ...,
    file: Annotated[UploadFile, File(description="A PNG or JPEG histopathology patch.")],
    include_explanation: Annotated[bool, Form()] = False,
    client_reference: Annotated[str | None, Form(max_length=100)] = None,
) -> HistopathologyPredictionResponse:
```

**Częsty błąd początkującego**: próba przyjęcia obrazu jako pola w modelu Pydantic body (`class Request(BaseModel): file: bytes`). FastAPI/Pydantic obsługuje to inaczej niż pliki — `UploadFile` to strumień (`SpooledTemporaryFile` pod maską), nie zwykłe pole JSON, i wymaga `File(...)`/`Form(...)` razem w jednej funkcji, nie osobnego modelu body.

**Pytanie rekrutacyjne**: Co różni `UploadFile.read()` od `UploadFile.file.read()` pod względem tego, czy operacja jest asynchroniczna?

---

## 7. Streamowane wczytywanie z limitem bajtów

`Content-Length` to nagłówek, który klient *deklaruje* — nic nie gwarantuje, że odpowiada rzeczywistej liczbie wysłanych bajtów. Limit rozmiaru musi więc być liczony z tego, co faktycznie odebrano, kawałek po kawałku, nie z deklaracji.

**Gdzie w repo**: `app/services/prediction.py::read_upload_within_limit`.

```python
while True:
    chunk = await file.read(_UPLOAD_CHUNK_BYTES)  # 64 KiB na raz
    if not chunk:
        break
    total += len(chunk)
    if total > max_bytes:
        raise translate_inference_error(UploadTooLargeError(...))
    chunks.append(chunk)
```

**Częsty błąd początkującego**: wywołanie `await file.read()` bez argumentu (czyli "wczytaj wszystko na raz") i sprawdzenie limitu *po* tym wczytaniu. To już jest za późno — pamięć została zaalokowana, niezależnie od tego, czy później rzucisz błąd. Sprawdzanie musi się dziać *podczas* czytania, żeby przerwać wcześnie.

**Pytanie rekrutacyjne**: Czemu rozmiar fragmentu (`_UPLOAD_CHUNK_BYTES = 64 * 1024`) jest stałą, a nie np. `max_bytes` (czytaj wszystko za jednym zamachem do limitu)? Co by się zmieniło, gdyby był równy `max_bytes`?

---

## 8. Decompression bomb — mały plik, gigantyczny obraz

Skompresowany format obrazu może opisywać znacznie więcej pikseli niż sugeruje rozmiar pliku na dysku (skrajny przypadek: kilka KB pliku → gigabajty po zdekodowaniu). Pillow ma wbudowaną ochronę, ale jej domyślny próg jest bardzo wysoki — trzeba go jawnie zaostrzyć do własnego limitu.

**Gdzie w repo**: `medrisk_inference/image_validation.py::_decode`.

```python
Image.MAX_IMAGE_PIXELS = max_pixels  # własny, niższy limit - ustawiony PRZED dekodowaniem
with warnings.catch_warnings():
    warnings.simplefilter("error", Image.DecompressionBombWarning)
    probe = Image.open(BytesIO(data))
    probe.verify()
    image = Image.open(BytesIO(data))
    image.load()
```

**Częsty błąd początkującego**: sprawdzanie `width * height` *po* `image.load()` i licznie na to, że to wystarczy. Samo `.load()` już zdekodowało (i zaalokowało pamięć dla) całego obrazu — sprawdzenie wymiarów po fakcie nie zapobiega zużyciu pamięci, tylko odrzuca wynik. Stąd `Image.MAX_IMAGE_PIXELS` musi być ustawiony *przed* dekodowaniem, nie po.

**Pytanie rekrutacyjne**: `probe.verify()` jest wołane przed drugim `Image.open(...).load()` na tych samych bajtach. Po co dekodować dwa razy, zamiast raz?

---

## 9. EXIF i metadane — usuwanie przez rekonstrukcję, nie filtrowanie

Zdjęcie może nieść dane GPS, model aparatu, numer seryjny, komentarze — w polu `.info` obiektu Pillow. Wymienianie "co wolno, a co nie" w takim słowniku to gra w kotka i myszkę z formatami plików, które wciąż dodają nowe pola metadanych.

**Gdzie w repo**: `medrisk_inference/image_validation.py::validate_image_bytes`, ostatni krok.

```python
oriented = ImageOps.exif_transpose(image) or image  # zastosuj orientację, potem ZGUB tag EXIF
rgb_source = oriented.convert("RGB")
fresh_rgb = Image.frombytes("RGB", rgb_source.size, rgb_source.tobytes())  # nowy obiekt, bez .info
```

**Częsty błąd początkującego**: próba "wyczyszczenia" metadanych przez `image.info.clear()` albo podobne wywołanie na *istniejącym* obiekcie. To, czy taka operacja faktycznie usuwa wszystko, zależy od konkretnego formatu i wersji Pillow — znacznie bezpieczniejsze jest zbudowanie zupełnie nowego obiektu z samych bajtów pikseli, dla którego `.info` nigdy nie istniało.

**Pytanie rekrutacyjne**: `ImageOps.exif_transpose()` jest wołane *przed* odrzuceniem EXIF, nie po. Co konkretnie by się stało z obrazem zrobionym telefonem "w pionie", gdyby ta kolejność była odwrotna (najpierw zgub EXIF, potem próbuj transponować)?

---

## 10. Deklarowany kontra rzeczywisty typ MIME

Nagłówek `Content-Type` to też deklaracja klienta, tak jak `Content-Length` (punkt 7) — może być błędny albo złośliwie ustawiony. Jedyne wiarygodne źródło prawdy o formacie to to, co Pillow faktycznie zdekodowało.

**Gdzie w repo**: `medrisk_inference/image_validation.py`.

```python
_CONTENT_TYPE_BY_FORMAT = {"PNG": {"image/png"}, "JPEG": {"image/jpeg", "image/jpg"}}
...
allowed_content_types = _CONTENT_TYPE_BY_FORMAT.get(declared_format, set())
if declared_content_type.lower() not in allowed_content_types:
    raise ImageMimeMismatchError(...)
```

**Częsty błąd początkującego**: ufanie `Content-Type` jako jedynemu sprawdzeniu formatu (bez w ogóle dekodowania obrazu), albo odwrotnie — całkowite ignorowanie `Content-Type` i sprawdzanie tylko tego, co zdekodował Pillow. Ten projekt robi oba sprawdzenia i wymaga, by się zgadzały — niezgodność jest sama w sobie sygnałem czegoś podejrzanego, nawet jeśli plik "by przeszedł" samo dekodowanie.

**Pytanie rekrutacyjne**: Klient wysyła prawdziwy plik PNG, ale z nagłówkiem `Content-Type: image/jpeg`. Czy ten projekt to odrzuci, i jakim kodem błędu?

---

## 11. Kolejność walidacji ma znaczenie

Dwa różne sprawdzenia mogą obie "być prawdą" dla tego samego pliku (np. plik jest jednocześnie w nieobsługiwanym formacie *i* animowany) — który komunikat błędu klient zobaczy zależy wyłącznie od kolejności sprawdzeń w kodzie.

**Gdzie w repo**: `medrisk_inference/image_validation.py` — komentarz wprost wyjaśniający decyzję.

```python
# Format is checked before frame count: a file in an unsupported format should be
# rejected for that reason regardless of whether it happens to be animated too.
declared_format = image.format or ""
if declared_format not in SUPPORTED_IMAGE_FORMATS:
    raise UnsupportedImageFormatError(...)
if getattr(image, "n_frames", 1) > 1:
    raise ImageMultiFrameNotSupportedError(...)
```

**Częsty błąd początkującego**: traktowanie kolejności sprawdzeń jako nieistotnego szczegółu implementacyjnego. W tym konkretnym kodzie kolejność była odwrotna w pierwszej wersji — animowany GIF (zupełnie nieobsługiwany format) zwracał błąd "wielo-ramkowy", co jest mylące: klient mógłby pomyśleć, że pojedynczoramkowy GIF by zadziałał (nie zadziałałby — GIF nie jest wsparty wcale).

**Pytanie rekrutacyjne**: Jaki konkretny test (jakie dane wejściowe) odróżniłby implementację z poprawną kolejnością od tej z odwrotną?

---

## 12. Ścisły kontrakt wymiarów wejścia — czemu nie ma "resize-to-fit"

Model został wyewaluowany na obrazach o jednym, konkretnym rozmiarze (`manifest.input_height`/`input_width`). Automatyczne przeskalowanie dowolnego rozmiaru wejścia do tego rozmiaru *zadziałałoby* technicznie (PyTorch nie zaprotestuje), ale wprowadziłoby dane spoza rozkładu, na którym liczono metryki.

**Gdzie w repo**: `medrisk_inference/service.py::validate_upload`, włączane przez `STRICT_MODEL_INPUT_SHAPE=true` (domyślnie).

```python
if runtime.config.strict_model_input_shape:
    if validated_image.width != manifest.input_width or validated_image.height != manifest.input_height:
        raise ImageDimensionsInvalidError(
            f"Image dimensions {validated_image.width}x{validated_image.height} do not match "
            f"the required {manifest.input_width}x{manifest.input_height} input shape."
        )
```

**Częsty błąd początkującego**: mylenie "model przyjmie ten tensor bez błędu" z "wynik modelu na tym tensorze jest sensowny". `T.Resize` w transformacji ewaluacyjnej *też* technicznie istnieje i też by "zadziałało" na obrazie złej wielkości — różnica to, czy przeskalowanie jest częścią udokumentowanego, wyewaluowanego pipeline'u, czy cichym dodatkiem na granicy API.

**Pytanie rekrutacyjne**: Co konkretnie by się zmieniło w ocenie modelu (metrics.json z Fazy 2), gdyby ten projekt zamiast odrzucać złe wymiary, po prostu doklejał `T.Resize(manifest.input_height)` na początku pipeline'u inferencji?

---

## 13. Sigmoid liczony numerycznie stabilnie

Matematyczna definicja sigmoidu (`1 / (1 + e^-x)`) potrafi przekroczyć zakres liczb zmiennoprzecinkowych dla dużych ujemnych `x` (ogromne `e^-x`) — trzeba ją policzyć inaczej w zależności od znaku argumentu.

**Gdzie w repo**: `medrisk_inference/decision.py::sigmoid`.

```python
def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)        # x < 0, więc exp(x) jest mały i bezpieczny
    return exp_x / (1.0 + exp_x)
```

**Częsty błąd początkującego**: napisanie sigmoidu w jednej linii (`1 / (1 + math.exp(-x))`) bez rozróżnienia znaku `x`. Dla `x = -1000` to rzuci `OverflowError` w czystym Pythonie (`math.exp(1000)` przekracza zakres `float`) — co jest szczególnie podstępne, bo dla "normalnych" logitów z dobrze wytrenowanego modelu nigdy się to nie zdarzy, więc błąd ujawnia się tylko na skrajnych/błędnych wejściach.

**Pytanie rekrutacyjne**: PyTorch ma `torch.sigmoid`, które jest numerycznie stabilne "za darmo". Czemu `medrisk_inference/decision.py` definiuje własny, czysto-Pythonowy `sigmoid()`, zamiast użyć `torch.sigmoid` na tensorze?

---

## 14. Temperature scaling — kalibracja jako funkcja czysta

Surowy logit z modelu, po sigmoidzie, daje "prawdopodobieństwo" które bywa systematycznie nadmiernie pewne siebie. Temperature scaling to jeden dodatkowy, wyuczony w Fazie 2 (na zbiorze walidacyjnym) skalar `T`, dzielący logit przed sigmoidem — i nic więcej.

**Gdzie w repo**: `medrisk_inference/decision.py::apply_calibration`. Parametr `temperature` jest czytany z `calibration.json` w bundlu — nigdy ponownie dopasowywany w czasie inferencji.

```python
temperature = (calibration or {}).get("temperature")
probability = sigmoid(logit) if temperature is None else sigmoid(logit / temperature)
```

**Częsty błąd początkującego**: mylenie kalibracji z "poprawianiem" predykcji modelu. Temperature scaling nigdy nie zmienia *kolejności* przykładów po prawdopodobieństwie (monotoniczna transformacja) — nie zmienia więc ROC-AUC ani tego, które przykłady są błędne. Zmienia tylko to, *jak bardzo pewne* liczby model zwraca, co ma znaczenie dopiero, gdy porównujesz prawdopodobieństwo z progiem albo z pasmem przeglądu (punkt 15).

**Pytanie rekrutacyjne**: Jeśli `temperature > 1`, w którą stronę "ściska" się rozkład wynikowych prawdopodobieństw (bliżej 0.5, czy bliżej 0/1) względem surowego sigmoidu?

---

## 15. Próg + `review_policy` = trzy-kierunkowa decyzja

Faza 2 zostawiła w manifeście pole `review_policy`, którego nic jeszcze nie czytało (dosłownie zadanie domowe w przewodniku do Fazy 2). Faza 3 to ten brakujący kawałek: pasmo niepewności wokół progu, które kwalifikuje wynik do przeglądu przez człowieka, zamiast wymuszać binarną decyzję.

**Gdzie w repo**: `medrisk_inference/decision.py::decide`.

```python
if review_policy is not None:
    if calibrated_probability <= review_policy.negative_probability_max:
        decision = "negative"
    elif calibrated_probability >= review_policy.positive_probability_min:
        decision = "positive"
    else:
        decision = "review_required"
```

**Częsty błąd początkującego**: zakładanie, że `predicted_class` i `decision` to to samo pole pod dwoma nazwami. `predicted_class` to *zawsze* czysty podział progowy (informacyjny nawet w paśmie przeglądu); `decision` to finalny, świadomy-polityki werdykt — w paśmie przeglądu te dwa pola legalnie "się nie zgadzają", i to jest zamierzone, nie błąd.

**Pytanie rekrutacyjne**: Bundle ma `threshold=0.5` i `review_policy={negative_probability_max: 0.3, positive_probability_min: 0.7}`. Dla `calibrated_probability=0.4`, jaki będzie `predicted_class`, a jaki `decision`?

---

## 16. `torch.inference_mode()`

Tryb wnioskowania PyTorch jest ściślejszy niż `torch.no_grad()` — wyłącza nie tylko śledzenie gradientów, ale też część księgowości autograd, którą `no_grad()` wciąż zachowuje "na wszelki wypadek" (np. możliwość włączenia gradientu z powrotem na tensorze w trakcie blocku).

**Gdzie w repo**: `medrisk_inference/runtime.py::predict` i `warmup`.

```python
with torch.inference_mode():
    output = self.model(tensor)
```

**Częsty błąd początkującego**: użycie `torch.no_grad()` w kodzie produkcyjnej inferencji "bo tak się zawsze robi" (typowe w skryptach treningowych/ewaluacyjnych, gdzie tensor czasem trzeba później użyć w gradient-zależnym kontekście). W czysto-inferencyjnym kodzie, który nigdy nie potrzebuje gradientu z powrotem, `inference_mode()` jest strictly lepsze i nie ma kosztu kompatybilności.

**Pytanie rekrutacyjne**: Co konkretnie by się stało (błąd, czy tylko gorsza wydajność), gdybyś spróbował wywołać `.backward()` na tensorze wyprodukowanym wewnątrz blocku `torch.inference_mode()`?

---

## 17. Warm-up modelu

Pierwsze wywołanie modelu na danym urządzeniu bywa wolniejsze niż kolejne — inicjalizacja kerneli CUDA/cuDNN, alokacja pamięci, JIT-owe ścieżki w bibliotekach. Warm-up to jedno, jednorazowe, fałszywe wywołanie *przy starcie*, żeby ten koszt nie spadł na pierwszego prawdziwego użytkownika.

**Gdzie w repo**: `medrisk_inference/runtime.py::warmup`, wołane automatycznie z `from_bundle`, gdy `MODEL_WARMUP_ENABLED=true`.

```python
dummy = torch.zeros(1, manifest.input_channels, manifest.input_height, manifest.input_width, device=self.device.device)
with torch.inference_mode():
    output = self.model(dummy)
logit = self._extract_logit(output)
apply_calibration(logit, self.calibration)  # ćwiczy też ścieżkę kalibracji, nie tylko forward()
```

**Częsty błąd początkującego**: warm-up, który woła tylko `self.model(dummy)` i kończy. Ten kod celowo woła też `apply_calibration` na wyniku — żeby błąd w samej kalibracji (np. źle sformatowane `calibration.json`) też zostanie wykryty *przy starcie*, zamiast przy pierwszym prawdziwym żądaniu.

**Pytanie rekrutacyjne**: `warmup()` ustawia `self._ready = False` *przed* próbą, i tylko `True` po sukcesie. Co by się stało z każdym żądaniem przychodzącym w trakcie trwania samego `warmup()` (zanim się zakończy, w obie strony)?

---

## 18. `asyncio.Semaphore` jako kontrola współbieżności

Jeden model w jednym procesie nie powinien (i przy `INFERENCE_MAX_CONCURRENCY=1`, na CPU, nie ma sensu próbować) obsługiwać wielu równoległych forward-passów naraz. Semafor to licznik pozwoleń: tyle żądań ile ma pozwoleń może być "w środku" jednocześnie, reszta czeka.

**Gdzie w repo**: `app/main.py` tworzy semafor raz; `app/services/prediction.py::_predict_with_concurrency_limit` go używa.

```python
try:
    await asyncio.wait_for(semaphore.acquire(), timeout=settings.INFERENCE_QUEUE_TIMEOUT_SECONDS)
except TimeoutError as exc:
    raise InferenceQueueFullError(...) from exc
try:
    ...  # właściwa inferencja
finally:
    semaphore.release()
```

**Częsty błąd początkującego**: zapominanie o `finally: semaphore.release()`. Bez tego, jeśli inferencja rzuci wyjątek, pozwolenie nigdy nie wraca do semafora — po kilku takich błędach semafor jest permanentnie "pusty" i *każde* kolejne żądanie czeka do timeoutu i dostaje 429, nawet gdy proces jest skądinąd zdrowy.

**Pytanie rekrutacyjne**: `INFERENCE_MAX_CONCURRENCY=1`. Trzy żądania przychodzą w tej samej milisekundzie. Ile z nich faktycznie wykonuje `self.model(tensor)` w tym samym momencie, a ile czeka na `semaphore.acquire()`?

---

## 19. `asyncio.to_thread` — nie blokuj event loop

PyTorch na CPU jest synchroniczny i blokujący — wewnątrz `async def` nie ma żadnego "await" punktu w samym forward-passie. Wywołanie go bezpośrednio w korutynie zamroziłoby *cały* event loop (czyli wszystkie inne, niezwiązane żądania — logowanie, historię, health-check) na czas trwania inferencji.

**Gdzie w repo**: `app/services/prediction.py::_predict_with_concurrency_limit`.

```python
await asyncio.wait_for(
    asyncio.to_thread(run_validated_inference, runtime, validated_image, ...),
    timeout=settings.INFERENCE_TIMEOUT_SECONDS,
)
```

**Częsty błąd początkującego**: wywołanie `run_validated_inference(...)` bezpośrednio (bez `to_thread`) wewnątrz `async def`, bo "to tylko jedna linijka, nie powinno zaszkodzić". Pod małym obciążeniem rzeczywiście nie widać różnicy — różnica ujawnia się tylko przy współbieżnych żądaniach, co czyni ten błąd szczególnie łatwym do przegapienia na etapie ręcznego testowania.

**Pytanie rekrutacyjne**: Gdyby `INFERENCE_MAX_CONCURRENCY` było równe 4 (zamiast 1), ale `run_validated_inference` było wołane bez `asyncio.to_thread` — czy cztery wywołania faktycznie wykonywałyby się współbieżnie?

---

## 20. Dwa różne rodzaje "czasu oczekiwania"

"Żądanie czeka długo" może znaczyć dwie zupełnie różne rzeczy: czeka w kolejce o dostęp do modelu, albo model już pracuje i po prostu trwa to długo. To dwa odrębne timeouty, z dwoma odrębnymi kodami błędów.

**Gdzie w repo**: `INFERENCE_QUEUE_TIMEOUT_SECONDS` (domyślnie 5s, → `429 INFERENCE_QUEUE_FULL` z nagłówkiem `Retry-After`) kontra `INFERENCE_TIMEOUT_SECONDS` (domyślnie 20s, → `504 INFERENCE_TIMEOUT`) — patrz kod w punkcie 18 i 19.

```python
class InferenceQueueFullError(AppError):
    status_code = 429
    def __init__(self, message=None, *, retry_after_seconds=1):
        super().__init__(message, headers={"Retry-After": str(retry_after_seconds)})
```

**Częsty błąd początkującego**: łączenie obu w jeden timeout "na całość żądania". To zaciera ważną różnicę dla klienta: `429` mówi "spróbuj ponownie za chwilę, system jest zajęty, ale działa", `504` mówi "coś trwało nienaturalnie długo, prawdopodobnie problem z samym modelem/danymi" — to dwie różne akcje naprawcze.

**Pytanie rekrutacyjne**: Dlaczego `InferenceQueueFullError` ma nagłówek `Retry-After`, a `InferenceTimeoutError` (504) — nie?

---

## 21. Granica transakcji bazy danych wokół wolnej operacji

Reguła z Fazy 1 ("warstwa serwisu commit'uje") dostaje w Fazie 3 dodatkowe, krytyczne zastrzeżenie: transakcja nie może obejmować wolnej, niededykowanej-do-bazy operacji (forward pass modelu).

**Gdzie w repo**: `app/services/prediction.py::run_histopathology_prediction`.

```python
prediction = await prediction_repo.create_pending(session, ...)
await session.commit()                       # commit #1 - transakcja ZAMKNIĘTA
result = await _predict_with_concurrency_limit(...)   # może trwać sekundy, BEZ otwartej transakcji
await prediction_repo.mark_completed(session, prediction, ...)
await session.commit()                        # commit #2
```

**Częsty błąd początkującego**: otwarcie jednej transakcji na cały endpoint ("insert na początku, update na końcu, jeden commit") — co wygląda prościej, ale oznacza, że transakcja (i jej blokady na poziomie bazy) jest otwarta przez cały czas trwania inferencji. Przy współbieżnych żądaniach to może prowadzić do długo trzymanych blokad na zupełnie niezwiązanych operacjach.

**Pytanie rekrutacyjne**: Żądanie pada w trakcie samej inferencji (np. timeout). Ile wierszy `predictions` istnieje w bazie po tym zdarzeniu, i w jakim stanie (`status`)?

---

## 22. Mapowanie błędów domenowych na HTTP — bezpieczne komunikaty 5xx

Wyjątek z `medrisk_inference` ma `error_code` (bezpieczny do pokazania) i `message` (może opisywać stan wewnętrzny, niebezpieczny do pokazania). Które dokładnie pole klient zobaczy zależy od klasy statusu, nie od konkretnego kodu błędu.

**Gdzie w repo**: `app/services/prediction.py::translate_inference_error`.

```python
def translate_inference_error(exc: InferenceError) -> AppError:
    status_code = _STATUS_BY_ERROR_CODE.get(exc.error_code, 500)
    message = exc.message if status_code < 500 else _GENERIC_SERVER_MESSAGE
    return AppError(message, error_code=exc.error_code, status_code=status_code)
```

**Częsty błąd początkującego**: zakładanie, że "wiadomość z wyjątku" jest z definicji bezpieczna do pokazania, bo "to ja ją napisałem, w moim kodzie". `ModelOutputInvalidError`, dla przykładu, może w swojej wiadomości zawierać kształt tensora albo szczegóły wewnętrznego stanu modelu — przydatne w logu serwera, bezsensowne (i potencjalnie informacyjne dla atakującego) w odpowiedzi HTTP.

**Pytanie rekrutacyjne**: `IMAGE_DIMENSIONS_INVALID` to kod 422 (4xx) — jego wiadomość *jest* pokazywana klientowi w pełni. Czemu to jest bezpieczne, w odróżnieniu od `MODEL_OUTPUT_INVALID` (500)?

---

## 23. Grad-CAM, który nigdy nie psuje predykcji

Wygenerowanie mapy Grad-CAM to operacja *opcjonalna i dodatkowa* względem samej predykcji — jej porażka nie powinna zamienić udanej predykcji w błąd 500.

**Gdzie w repo**: `medrisk_inference/runtime.py::explain` — `try/except` żyje na poziomie runtime'u, nie wywołującego kodu, więc gwarancja obowiązuje dla *każdego* przyszłego wołającego, nie tylko dla obecnego API.

```python
def explain(self, outcome, validated_image) -> ExplanationResult:
    """Never raises: ..."""
    try:
        with self._explain_lock:
            return generate_explanation(...)
    except (ExplanationFailedError, ExplanationNotSupportedError) as exc:
        return ExplanationResult(status="failed", error_code=exc.error_code)
```

**Częsty błąd początkującego**: umieszczenie tego `try/except` tylko w warstwie API/serwisu (bo "to tam wiemy, jak budować bezpieczną odpowiedź HTTP"), a nie w samym `runtime.explain()`. To zostawia pułapkę: każdy inny kod wołający `runtime.explain()` bezpośrednio (np. CLI, przyszły batch-job) odzyskuje surowy wyjątek, bo gwarancja "nigdy nie rzuca" żyła tylko jedno wywołanie wyżej.

**Pytanie rekrutacyjne**: `self._explain_lock` to `threading.Lock()`, nie `asyncio.Lock()`. Czemu, biorąc pod uwagę, że `explain()` jest wołane z wnętrza `asyncio.to_thread(...)` (patrz punkt 19)?

---

## 24. Audyt deploymentów modelu i brak hot-swap

Każda *próba* wczytania modelu — udana czy nie — dostaje własny wiersz w `model_deployments`. To dziennik tego, co było aktywne kiedy, nie tylko wskaźnik na "aktualny" model.

**Gdzie w repo**: `app/services/model_deployment.py` — `create` (status `loading`) → `mark_active`/`mark_failed` → `deactivate_previous_active`.

```python
deployment = await deployment_repo.create(session, ..., status domyślnie LOADING)
await session.commit()
try:
    runtime = HistopathologyModelRuntime.from_bundle(bundle, config)
except InferenceError as exc:
    await deployment_repo.mark_failed(session, deployment, failure_code=exc.error_code)
    ...
```

**Częsty błąd początkującego**: oczekiwanie zmiany modelu "na żywo" przez np. zmianę zmiennej środowiskowej bez restartu procesu. Nie ma żadnego mechanizmu (endpoint, sygnał, file-watcher), który by to zrobił — `MODEL_BUNDLE_PATH` jest czytane wyłącznie raz, w `lifespan`, przy starcie. Zmiana modelu = restart procesu, zawsze.

**Pytanie rekrutacyjne**: Czemu wiersze w `model_deployments` nigdy nie są usuwane przy aktywacji nowego modelu, tylko oznaczane jako `inactive`?

---

## 25. Import isolation — sprawdzane podprocesem, nie tylko "na oko"

Twierdzenie "ten obraz Dockera nie potrzebuje pandas/scikit-learn/matplotlib" jest łatwo złamać przypadkowo (jeden nieopatrzny `import` w głębi modułu) i trudno zweryfikować samym czytaniem kodu — trzeba to faktycznie wykonać w czystym środowisku.

**Gdzie w repo**: `tests/inference/test_import_isolation.py` — odpala nowy interpreter Pythona jako podproces i sprawdza `sys.modules` *po* zaimportowaniu `medrisk_inference`.

```python
result = subprocess.run(
    [sys.executable, "-c", "import medrisk_inference.runtime; import sys; print(','.join(sys.modules))"],
    capture_output=True, text=True, check=True,
)
imported = set(result.stdout.strip().split(","))
forbidden = {"pandas", "sklearn", "matplotlib", "tensorboard", "h5py", "yaml"}
assert not (forbidden & imported)
```

**Częsty błąd początkującego**: sprawdzanie tego samego faktu w tym samym procesie testowym, który (przez inne testy, albo przez sam pytest) może już mieć część tych bibliotek załadowanych w `sys.modules` z zupełnie innego powodu — dając fałszywie negatywny (czyli niewykrywający problemu) wynik. Podproces startuje z czystym `sys.modules`, więc test mierzy dokładnie to, co deklaruje mierzyć.

**Pytanie rekrutacyjne**: `tqdm` był pierwotnie na liście zakazanych modułów w tym teście, a potem usunięty. Jak myślisz, dlaczego — i co to mówi o różnicy między "`medrisk_inference` importuje X" a "X jest w `sys.modules` po zaimportowaniu `medrisk_inference`"?

---

## 26. Test deterministyczny bez prawdziwego treningu — "wyzeruj ostatnią warstwę"

Testy integracyjne potrzebują w pełni przewidywalnego modelu (ten sam wynik za każdym razem, na żądanie), ale wytrenowanie prawdziwego modelu dla każdego przebiegu testów byłoby zarówno wolne, jak i niedeterministyczne.

**Gdzie w repo**: `tests/inference/fixtures/builder.py::build_constant_output_bundle` — buduje model przez normalną fabrykę (`medrisk_ml.models.factory.build_model`), a potem jawnie zeruje wagi i bias ostatniej warstwy klasyfikującej.

```python
with torch.no_grad():
    model.classifier[-1].weight.zero_()
    model.classifier[-1].bias.zero_()
# Każde wejście -> logit dokładnie 0.0 -> sigmoid(0.0) = 0.5, zawsze
```

**Częsty błąd początkującego**: mockowanie (`unittest.mock`) całego `HistopathologyModelRuntime` albo `torch.nn.Module.forward`, żeby "zwracał stałą". To przetestowałoby kod *wokół* modelu, ale nie przetestowałoby prawdziwego ładowania bundla, prawdziwej budowy modelu z fabryki, prawdziwego `load_state_dict`, prawdziwego forward-passu na prawdziwym urządzeniu — czyli właśnie tych miejsc, gdzie błędy integracyjne faktycznie się zdarzają. Wyzerowanie wag daje deterministyczny wynik *bez* mockowania żadnej z tych prawdziwych ścieżek.

**Pytanie rekrutacyjne**: `review_policy` w testowym bundlu jest ustawione na `{negative_probability_max: 0.3, positive_probability_min: 0.7}`. Skoro każda predykcja daje `calibrated_probability=0.5`, jaki `decision` dostanie **każde** żądanie w testach integracyjnych, i czemu to jest świadomy wybór (patrz punkt 15), a nie przypadek?

---

## Pytania kontrolne

1. Dlaczego `app.state.histopathology_model` jest ustawiane na `None` *przed* próbą wczytania modelu w `lifespan`, a nie tylko raz, po sukcesie?
2. Co konkretnie odróżnia `ModelStartupError` od `InferenceError` — czemu to dwie różne hierarchie wyjątków?
3. Gdyby `MODEL_BUNDLE_PATH` wskazywał na bundle z `synthetic_only=true`, a `ENVIRONMENT=production` — w którym konkretnie miejscu kodu (i ile razy) ten bundle zostałby odrzucony?
4. Czemu `_ensure_no_symlink_escape` sprawdza każdy plik z `BUNDLE_FILES` osobno, a nie po prostu cały katalog bundla raz?
5. Jaka jest różnica między `IMAGE_PIXEL_LIMIT_EXCEEDED` zgłoszonym przez `Image.MAX_IMAGE_PIXELS`/`DecompressionBombWarning`, a tym samym kodem błędu zgłoszonym przez bezpośrednie sprawdzenie `width * height > config.max_image_pixels`?
6. Dlaczego `ValidatedImage.sha256` jest liczone z *oryginalnych* bajtów uploadu, a nie z bajtów już-zwalidowanego, oczyszczonego bufora RGB?
7. Co konkretnie różni `predicted_class_probability` od `calibrated_probability` w `DecisionResult`?
8. Czemu `runtime.predict()` rzuca `ModelNotReadyError`, sprawdzając `self._ready`, mimo że ten sam runtime już raz przeszedł przez `warmup()` przy starcie?
9. Jaką rolę odgrywa `bundle_sha256` na wierszu `model_deployments`, w odróżnieniu od `model_version`?
10. Dlaczego `read_upload_within_limit` jest wołane *przed* `validate_histopathology_upload`, a nie po?
11. Co dokładnie zwróci endpoint, jeśli klient wyśle prawidłowy obraz, ale aktualny model jest w trakcie `warmup()` (jeszcze nie `ready`)?
12. Czemu `HistopathologyPredictionResponse` ma pole `explanation` zawsze obecne (nigdy `None`), nawet gdy `include_explanation=False`?
13. Jaka jest różnica między tym, co loguje `logger.warning` w ścieżce błędu `AppError`, a tym, co loguje `logger.exception` w ścieżce nieprzewidzianego wyjątku, w `run_histopathology_prediction`?
14. Dlaczego `Dockerfile.inference` instaluje torch z `--index-url https://download.pytorch.org/whl/cpu` jako osobny krok, zamiast po prostu umieścić `torch` w `requirements-inference.txt`?
15. Co dokładnie się stanie (i ile wierszy `predictions` powstanie), jeśli ten sam użytkownik wyśle dokładnie ten sam plik obrazu dwa razy pod rząd?

## Zadania do samodzielnego wykonania

Wszystkie można wykonać lokalnie na syntetycznym bundlu (`artifacts/model_registry/smoke-baseline-cnn/0.0.1-smoke`, `ALLOW_SYNTHETIC_MODEL=true`), bez żadnego prawdziwego modelu PCam. Uruchom pełny `pytest` przed i po, żeby upewnić się, że nic istniejącego nie przestało działać.

1. **Dodaj limit liczby żądań na użytkownika.** `INFERENCE_MAX_CONCURRENCY` ogranicza globalną współbieżność procesu, ale nic nie ogranicza, ile żądań *ten sam* użytkownik może mieć w toku naraz. Zaprojektuj (i zaimplementuj) prosty licznik per-`user_id`, z testem na dwa równoległe żądania tego samego użytkownika.
2. **Dodaj endpoint deaktywacji modelu.** Bez zmiany zasady "jeden model na proces", dodaj endpoint administracyjny, który ustawia istniejący aktywny `ModelDeployment` na `inactive` i `app.state.histopathology_model = None` — sprawdź, że kolejne żądania predykcji dostają `503 MODEL_NOT_CONFIGURED` od razu po tym wywołaniu.
3. **Napisz test na dwa równoczesne żądania pod `INFERENCE_MAX_CONCURRENCY=1`.** Użyj np. monkeypatchu spowalniającego `runtime.predict` (`time.sleep`/krótkie opóźnienie) i `asyncio.gather` dwóch żądań naraz — zweryfikuj, że drugie żądanie faktycznie czekało (zmierz czas), a nie tylko że oba się skończyły sukcesem.
4. **Dodaj nowy format obrazu.** Rozszerz `SUPPORTED_IMAGE_FORMATS` o `WEBP` (bez utraty: nadal odrzucaj animowane wersje, nadal sprawdzaj zgodność MIME). Napisz test pozytywny i upewnij się, że istniejące testy negatywne (np. BMP) wciąż przechodzą.
5. **Zaimplementuj rzeczywiste sprawdzenie `MODEL_STRICT_VERSION_CHECK`.** Dodaj opcjonalne pole `torch_version`/`python_version` do procesu budowania bundla w Fazie 2 (`medrisk_ml/registry/bundle.py`), zapisz je w manifeście, i zaimplementuj w `medrisk_inference/bundle.py::load_bundle` faktyczne porównanie z `torch.__version__`/`sys.version` w czasie wczytywania — z testem na niezgodną wersję.
6. **Dodaj metrykę "czas oczekiwania w kolejce" do odpowiedzi.** `TimingsSchema` ma `validation_ms`/`preprocessing_ms`/etc., ale nie ma czasu spędzonego czekając na semafor. Zmierz go w `_predict_with_concurrency_limit` i dodaj jako nowe, opcjonalne pole.
7. **Napisz test na uszkodzony plik `calibration.json`.** Zbuduj bundle testowy (na bazie `build_constant_output_bundle`) z nieprawidłową wartością `temperature` (np. `0` albo ujemną) i zweryfikuj, że `warmup()` (nie dopiero pierwsze prawdziwe żądanie) wykrywa to i ustawia model jako `not ready`.
8. **Zaimplementuj prosty rate limiter dla `/predictions/histopathology`** (niezależny od `INFERENCE_MAX_CONCURRENCY`) — np. sliding window per użytkownik — i udokumentuj w komentarzu, czym różni się od istniejącej kontroli współbieżności (semafora).
