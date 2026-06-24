# Faza 2: Fundament ML dla histopatologii — przewodnik edukacyjny

Ten dokument jest napisany dla osoby, która umie programować (np. znana z Fazy 1: FastAPI, Python), ale dopiero zaczyna pracę z uczeniem maszynowym, PyTorch i obrazową klasyfikacją binarną. Każda sekcja: proste wyjaśnienie → gdzie to jest w tym repozytorium → krótki przykład kodu → częsty błąd początkującego → pytanie w stylu rekrutacyjnym.

> Przypomnienie obowiązujące w całej Fazie 2: to projekt edukacyjny/badawczy. Żaden wynik (zwłaszcza na danych syntetycznych) nie jest i nie może być prezentowany jako wydajność medyczna. Pełny disclaimer: *"This software is an educational and research portfolio project. It is not a medical device and must not be used for diagnosis, treatment decisions, or emergency medical guidance."*

---

## 1. Uczenie maszynowe nadzorowane (supervised learning)

Uczenie nadzorowane to trenowanie modelu na parach (dane wejściowe, poprawna etykieta), tak by nauczył się funkcji przewidującej etykietę dla nowych, niewidzianych wcześniej danych. W Fazie 2 wejściem jest obraz histopatologiczny 96×96 px, etykietą — `0` (brak tkanki nowotworowej w centrum) lub `1` (jest).

**Gdzie w repo**: cały pakiet `medrisk_ml/` realizuje jeden problem nadzorowany: klasyfikację binarną PatchCamelyon (PCam).

```python
# medrisk_ml/data/synthetic.py — każda próbka to (obraz, etykieta, identyfikator)
def __getitem__(self, index: int) -> tuple[torch.Tensor, int, str]:
    ...
    return tensor, label, sample_id
```

**Częsty błąd początkującego**: mylenie "model się uczy" z "model zapamiętuje". Model nie zapamiętuje konkretnych obrazów treningowych (o ile nie jest przeuczony — patrz punkt 20) — uczy się ogólnych wzorców, które potem stosuje do nowych danych.

**Pytanie rekrutacyjne**: Czym różni się uczenie nadzorowane od nienadzorowanego, i do której kategorii należy klasteryzacja?

---

## 2. Klasyfikacja binarna

Klasyfikacja binarna to przewidywanie jednej z dwóch klas (tu: `negative` / `positive`). Model nie zwraca etykiety wprost — zwraca liczbę (logit albo prawdopodobieństwo), którą trzeba porównać z progiem decyzyjnym (punkt 41), żeby dostać `0`/`1`.

**Gdzie w repo**: `medrisk_ml/constants.py` — `CLASS_NAMES = ("negative", "positive")`. Cały pipeline jest napisany pod dokładnie dwie klasy, nigdy więcej — `model.num_classes` musi równać się `1` (jeden logit, nie dwa).

```python
# medrisk_ml/config.py
@field_validator("num_classes")
@classmethod
def _binary_only(cls, v: int) -> int:
    if v != 1:
        raise ValueError(
            "Only binary classification (num_classes=1, single logit output) is "
            "supported in Phase 2"
        )
    return v
```

**Częsty błąd początkującego**: zakładanie, że klasyfikacja binarna potrzebuje dwóch neuronów wyjściowych (jak klasyfikacja wieloklasowa z softmax). Wystarczy jeden logit + sigmoid — softmax na dwóch klasach matematycznie redukuje się do tego samego.

**Pytanie rekrutacyjne**: Czemu ten projekt wymusza `num_classes=1` zamiast pozwolić na `num_classes=2` z softmax na wyjściu?

---

## 3. Tensor

Tensor to wielowymiarowa tablica liczb (uogólnienie wektora/macierzy) — podstawowa struktura danych w PyTorch. Obraz, etykieta, wagi sieci, gradienty — wszystko to są tensory.

**Gdzie w repo**: dosłownie wszędzie w `medrisk_ml/`; np. `medrisk_ml/models/baseline_cnn.py::forward` przyjmuje i zwraca `torch.Tensor`.

```python
def forward(self, x: torch.Tensor) -> torch.Tensor:
    """Returns raw logits of shape (batch, 1)."""
    x = self.features(x)
    x = self.pool(x)
    logits: torch.Tensor = self.classifier(x)
    return logits
```

**Częsty błąd początkującego**: mylenie tensora PyTorch z tablicą NumPy. Wyglądają podobnie, ale tensor PyTorch dodatkowo śledzi gradienty (`requires_grad`) i może żyć na GPU — `.numpy()`/`torch.from_numpy()` konwertują między nimi, ale tylko gdy tensor jest na CPU i odłączony od grafu obliczeń (`.detach()`).

**Pytanie rekrutacyjne**: Co się stanie, jeśli spróbujesz wywołać `.numpy()` na tensorze, który jest na GPU i ma `requires_grad=True`, bez wcześniejszego `.cpu().detach()`?

---

## 4. Obraz jako tensor (kształt CHW)

Obraz RGB jest reprezentowany jako tensor o kształcie `(C, H, W)` — kanały (3 dla RGB), wysokość, szerokość — a nie `(H, W, C)`, jak to robi np. PIL/NumPy. Batch obrazów dodaje czwarty wymiar: `(B, C, H, W)`.

**Gdzie w repo**: `medrisk_ml/data/transforms.py::build_transform` — `T.ToTensor()` jest właśnie tym krokiem, który zamienia obraz PIL `(H, W, C)` na tensor `(C, H, W)` i skaluje wartości pikseli z `[0, 255]` do `[0.0, 1.0]`.

```python
ops.append(T.ToTensor())
ops.append(_normalization_for(architecture, mean, std))
```

**Częsty błąd początkującego**: ręczne wczytanie obrazu (np. przez `PIL.Image.open` + `np.array`) i przekazanie go do modelu bez `ToTensor()` — model dostanie kształt `(H, W, C)` zamiast `(C, H, W)`, a warstwa `Conv2d` zinterpretuje wymiary błędnie, bez wyraźnego błędu (czasem zadziała "przypadkiem", jeśli `H == C` numerycznie się zgadza).

**Pytanie rekrutacyjne**: Jaki konkretnie kształt tensora (4 liczby) wejdzie do `BaselineCNN.forward`, jeśli batch ma 16 obrazów 96×96 RGB?

---

## 5. Podział train/val/test

Trzy rozłączne podzbiory danych: `train` (uczenie wag), `val` (wybór hiperparametrów/progu/checkpointu — nigdy gradientów), `test` (jedna, ostateczna ocena na końcu). Pełne uzasadnienie i wymuszenie w kodzie: [docs/experiment-protocol.md](../experiment-protocol.md).

**Gdzie w repo**: `medrisk_ml/types.py::SplitName = Literal["train", "val", "test"]` — typowane na poziomie systemu typów, nie tylko jako string w dokumentacji.

```python
def select_threshold(..., split_name: str, ...) -> ThresholdResult:
    if split_name == "test":
        raise SplitLeakageError(
            "Threshold selection must use the validation split, not the test split"
        )
```

**Częsty błąd początkującego**: "podglądanie" wyniku na test secie w trakcie eksperymentowania ("sprawdzę tylko raz, dla pewności") i potem dostrajanie czegokolwiek na tej podstawie. To już jest wyciek danych — nawet bez zmiany kodu, sama wiedza "test AUC spadło, zmienię coś" zanieczyszcza wynik.

**Pytanie rekrutacyjne**: Programista uruchamia `evaluate` dwa razy dla tego samego eksperymentu, zmieniając między nimi `learning_rate` w configu i trenując od nowa, bo "test wynik był słaby przy pierwszym razie". Co jest nie tak z tą procedurą?

---

## 6. Wyciek danych (data leakage)

Wyciek danych to sytuacja, w której informacja, która w realnym wdrożeniu nie byłaby dostępna w momencie podejmowania decyzji, przedostaje się do procesu uczenia/ewaluacji — i sztucznie podwyższa zmierzoną jakość modelu.

**Gdzie w repo**: trzy konkretne, kodowe bariery przed wyciekiem: `SplitLeakageError` (próg/kalibracja tylko na `val`), `compute_normalization_stats` liczone tylko z `train` (patrz punkt 23), `deterministic_subset` używa permutacji ziarna, a nie pierwszych N rekordów (PCam na dysku nie jest zbalansowane klasowo).

```python
# medrisk_ml/data/statistics.py — sprawdzane w testach, nie tylko w komentarzu
split = getattr(dataset, "split", None)
if split != "train":
    raise ValueError("Normalization statistics must be computed from the train split only")
```

**Częsty błąd początkującego**: liczenie statystyk normalizacji (mean/std) z całego zbioru (train+val+test) "bo to wygodniejsze". To przemyca informację o rozkładzie danych walidacyjnych/testowych do preprocessing'u, który widzi też zbiór treningowy.

**Pytanie rekrutacyjne**: Dlaczego liczenie mean/std z całego datasetu (a nie tylko z train) jest formą wycieku danych, nawet jeśli etykiety nigdzie nie są używane w tym obliczeniu?

---

## 7. Epoka

Jedna epoka to jeden pełny przebieg przez cały zbiór treningowy (każda próbka widziana raz). Trening to zwykle wiele epok pod rząd.

**Gdzie w repo**: `medrisk_ml/training/trainer.py::fit` — główna pętla `for epoch in range(1, epochs + 1):`.

```python
for epoch in range(1, epochs + 1):
    final_epoch = epoch
    train_result = train_one_epoch(model, train_loader, optimizer, loss_fn, device, ...)
    val_result = evaluate(model, val_loader, loss_fn, device, ...)
```

**Częsty błąd początkującego**: mylenie epoki z krokiem (step/iteracją). Jedna epoka to wiele kroków — dokładnie `len(train_loader)` kroków, czyli liczba batchy, nie liczba próbek.

**Pytanie rekrutacyjne**: Jeśli zbiór treningowy ma 256 próbek, a `batch_size=16`, ile kroków optymalizacji (wywołań `optimizer.step()`) wykona jedna epoka?

---

## 8. Batch i batch size

Batch to porcja próbek przetwarzana razem w jednym kroku treningowym — kompromis między pojedynczą próbką (bardzo szumny gradient, wolne) i całym zbiorem (stabilny gradient, zbyt dużo pamięci). `batch_size` to liczba próbek w jednym batchu.

**Gdzie w repo**: `medrisk_ml/data/loaders.py::build_loader` — parametr `batch_size` przekazywany prosto do `torch.utils.data.DataLoader`.

```python
kwargs: dict[str, Any] = {
    "batch_size": batch_size,
    "shuffle": shuffle,
    "num_workers": num_workers,
    ...
}
```

**Częsty błąd początkującego**: zakładanie, że każdy batch ma identyczny rozmiar. Ostatni batch w epoce często jest mniejszy (np. 256 próbek / batch_size=16 = równo, ale 250/16 = 15 pełnych batchy + 1 batch po 10) — `drop_last=False` w tym projekcie świadomie zachowuje ten mniejszy batch, więc metryki muszą być liczone na połączonych wynikach z całej epoki, nie jako średnia po batchach (patrz punkt 9, docstring `engine.py`).

**Pytanie rekrutacyjne**: Czemu `medrisk_ml/training/engine.py` liczy ROC-AUC na skonkatenowanych logitach z całej epoki, a nie jako średnią ROC-AUC z każdego batcha?

---

## 9. Forward pass (przejście w przód)

Forward pass to przepuszczenie danych wejściowych przez sieć, warstwa po warstwie, do uzyskania wyjścia (tu: jednego logitu na obraz). To, dosłownie, wywołanie `model(x)`.

**Gdzie w repo**: `medrisk_ml/training/engine.py::_forward_logits` — jedyne miejsce w całym kodzie, gdzie wynik modelu `(batch, 1)` jest "ściskany" do `(batch,)`, tuż przed policzeniem straty.

```python
def _forward_logits(model: nn.Module, images: torch.Tensor) -> torch.Tensor:
    raw: torch.Tensor = model(images)
    return raw.squeeze(-1)
```

**Częsty błąd początkującego**: robienie `.squeeze(-1)` (albo nie robienie go) w wielu różnych miejscach kodu niekonsekwentnie. Gdyby model zwracał `(B, 1)`, a strata dostała to bez "ściśnięcia" razem z etykietą `(B,)`, `BCEWithLogitsLoss` *nie zgłosi błędu* — przez broadcasting policzy stratę na macierzy `(B, B)` zamiast wektora `(B,)`, co jest cichym, poważnym błędem.

**Pytanie rekrutacyjne**: Co dokładnie zwróci `nn.BCEWithLogitsLoss()(logits, labels)`, jeśli `logits` ma kształt `(8, 1)`, a `labels` ma kształt `(8,)` — błąd, czy liczba? Jaki to ma związek z broadcastingiem w NumPy/PyTorch?

---

## 10. Funkcja straty (loss function) i BCEWithLogitsLoss

Funkcja straty mierzy, jak bardzo przewidywanie modelu różni się od prawdziwej etykiety — liczba, którą trening próbuje zminimalizować. `BCEWithLogitsLoss` łączy sigmoid i binarną entropię krzyżową w jedną, numerycznie stabilną operację.

**Gdzie w repo**: `medrisk_ml/training/losses.py`.

```python
def build_loss(pos_weight: float | None = None) -> nn.Module:
    """`nn.BCEWithLogitsLoss`, optionally with a positive-class weight for imbalance."""
    weight_tensor = torch.tensor(pos_weight) if pos_weight is not None else None
    return nn.BCEWithLogitsLoss(pos_weight=weight_tensor)
```

**Częsty błąd początkującego**: ręczne robienie `nn.Sigmoid()` na wyjściu modelu, a potem `nn.BCELoss()` na prawdopodobieństwach. Ten rozkład jest numerycznie mniej stabilny — gdy sigmoid "nasyci się" blisko 0 lub 1, `BCELoss` może policzyć `log(0)` (czyli `-inf`/`NaN`). `BCEWithLogitsLoss` unika tego, licząc to wewnętrznie w sposób matematycznie równoważny, ale stabilny.

**Pytanie rekrutacyjne**: Czemu model w tym projekcie zwraca surowe logity, a nie prawdopodobieństwa, jeśli i tak gdzieś (np. przy liczeniu metryk) potrzebujemy prawdopodobieństw?

---

## 11. Gradient i backpropagation

Gradient to wektor pochodnych cząstkowych funkcji straty względem każdej wagi sieci — mówi, w którą stronę i jak silnie zmienić każdą wagę, żeby zmniejszyć stratę. Backpropagation (propagacja wsteczna) to algorytm efektywnego liczenia tych gradientów dla wszystkich warstw na raz, od wyjścia do wejścia.

**Gdzie w repo**: `medrisk_ml/training/engine.py::train_one_epoch` — `loss.backward()` to właśnie backpropagation; PyTorch robi to automatycznie dzięki grafowi obliczeń (autograd).

```python
loss = loss_fn(logits, labels_float) / accumulation_steps
...
scaler.scale(loss).backward()
```

**Częsty błąd początkującego**: zapominanie o `optimizer.zero_grad()` przed kolejnym `backward()`. PyTorch domyślnie *akumuluje* gradienty (dodaje nowe do starych) — bez wyzerowania, gradient z poprzedniego batcha "zanieczyściłby" bieżący.

**Pytanie rekrutacyjne**: Gradienty domyślnie się kumulują w PyTorch, a nie nadpisują. Jak ten projekt wykorzystuje to zachowanie *celowo* (zamiast traktować je tylko jako pułapkę do unikania)? Zobacz punkt 16.

---

## 12. Optimizer (AdamW / SGD)

Optimizer to algorytm aktualizujący wagi sieci na podstawie policzonych gradientów. `SGD` (stochastic gradient descent) to najprostszy wariant; `AdamW` adaptuje krok uczenia per-parametr i prawidłowo oddziela weight decay od gradientu (w przeciwieństwie do starszego `Adam` z `weight_decay` wmieszanym w sam gradient).

**Gdzie w repo**: `medrisk_ml/training/optimizer.py`.

```python
trainable_params = [p for p in model.parameters() if p.requires_grad]
if not trainable_params:
    raise ValueError("Model has no trainable parameters (everything is frozen)")
if name == "adamw":
    return torch.optim.AdamW(trainable_params, lr=learning_rate, weight_decay=weight_decay)
```

**Częsty błąd początkującego**: przekazanie do optimizera *wszystkich* parametrów modelu (`model.parameters()`), nawet zamrożonych. Tutaj filtrowane jest `requires_grad=True` — inaczej zamrożony backbone ResNet18 (punkt 31) dostałby (niepotrzebnie) miejsce w stanie optimizera.

**Pytanie rekrutacyjne**: Co dokładnie różni `AdamW` od `Adam` w sposobie traktowania `weight_decay`, i czemu ta różnica miała znaczenie historycznie (artykuł "Decoupled Weight Decay Regularization")?

---

## 13. Learning rate (krok uczenia)

Learning rate (współczynnik uczenia) skaluje, jak duży krok optimizer robi w stronę wskazanej przez gradient na każdej aktualizacji wag. Zbyt duży — trening "rozjeżdża się" (strata rośnie/oscyluje); zbyt mały — trening jest bardzo wolny lub zatrzymuje się w słabym minimum.

**Gdzie w repo**: `configs/ml/smoke.yaml` (`learning_rate: 0.001`) vs `configs/ml/resnet18.yaml` (`learning_rate: 0.0005`, niżej — bo dotyka wstępnie wytrenowanych wag).

```yaml
training:
  learning_rate: 0.001
  optimizer: adamw
```

**Częsty błąd początkującego**: używanie tego samego learning rate dla modelu od zera (`baseline_cnn`) i dla fine-tuningu pretrenowanego backbone'u (`resnet18`, stage B). Wagi pretrenowane są już w sensownym miejscu przestrzeni parametrów — duży krok może je szybko zepsuć (catastrophic forgetting, patrz punkt 32).

**Pytanie rekrutacyjne**: `configs/ml/resnet18.yaml` ma `learning_rate: 0.0005` dla Stage A (zamrożony backbone). Jaki rząd wielkości learning rate byłby sensowny dla Stage B (odmrożone `layer4`), i czemu znacznie niższy?

---

## 14. Weight decay

Weight decay to regularizacja, która lekko "ściąga" wagi modelu w stronę zera na każdym kroku, niezależnie od gradientu straty — zapobiega temu, by wagi rosły bez ograniczeń, co zwykle zmniejsza przeuczenie (punkt 20).

**Gdzie w repo**: `medrisk_ml/config.py::TrainingSection.weight_decay`, walidowane jako `>= 0`.

```python
@field_validator("weight_decay")
@classmethod
def _non_negative_weight_decay(cls, v: float) -> float:
    if v < 0:
        raise ValueError("training.weight_decay must be >= 0")
    return v
```

**Częsty błąd początkującego**: traktowanie weight decay jako "kolejnego hiperparametru do podkręcenia losowo". To wciąż forma regularyzacji — zbyt duża wartość niedouczy model (underfitting), tak jak zbyt mocny dropout (punkt 21).

**Pytanie rekrutacyjne**: Czym konceptualnie różni się weight decay od dropout — obie techniki "ograniczają" model, ale w zupełnie inny sposób. Jak?

---

## 15. Gradient clipping (przycinanie gradientu)

Gradient clipping ogranicza normę (długość) wektora gradientu do maksymalnej wartości przed krokiem optimizera — zapobiega "eksplodującym gradientom", które mogłyby jednym złym batchem zniszczyć wytrenowane wagi.

**Gdzie w repo**: `medrisk_ml/training/engine.py::train_one_epoch`, stosowane tylko w momencie faktycznej aktualizacji wag (po `accumulation_steps`, patrz punkt 16).

```python
if (step + 1) % accumulation_steps == 0:
    if grad_clip_norm is not None:
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip_norm)
    scaler.step(optimizer)
```

**Częsty błąd początkującego**: wywołanie `clip_grad_norm_` *przed* `scaler.unscale_()` przy używaniu mixed precision (punkt 19). Gradienty pod skalowaniem AMP są celowo wielokrotnie większe niż "prawdziwe" — przycięcie ich w tej postaci obcięłoby zupełnie inną (i niewłaściwą) wartość normy.

**Pytanie rekrutacyjne**: Dlaczego `scaler.unscale_(optimizer)` musi być wywołane przed `clip_grad_norm_`, a nie po?

---

## 16. Gradient accumulation (akumulacja gradientu)

Gradient accumulation pozwala symulować duży `batch_size` przy ograniczonej pamięci GPU: wykonujemy `backward()` na kilku mniejszych batchach pod rząd *bez* zerowania gradientu między nimi, i robimy `optimizer.step()` tylko raz na `accumulation_steps` batchy. To wykorzystuje domyślną akumulację gradientów PyTorch (punkt 11) celowo, nie przypadkiem.

**Gdzie w repo**: `medrisk_ml/training/engine.py::train_one_epoch`.

```python
loss = loss_fn(logits, labels_float) / accumulation_steps
...
scaler.scale(loss).backward()
if (step + 1) % accumulation_steps == 0:
    ...
    scaler.step(optimizer)
    scaler.update()
    optimizer.zero_grad(set_to_none=True)
```

**Częsty błąd początkującego**: zapominanie o podzieleniu straty przez `accumulation_steps`. Bez tego, sumaryczny gradient po N krokach byłby N razy większy niż dla pojedynczego dużego batcha o tym samym sumarycznym rozmiarze — efektywny learning rate zostałby przypadkowo przeskalowany.

**Pytanie rekrutacyjne**: `accumulation_steps=4` i `batch_size=16`. Jaki jest efektywny rozmiar batcha pod względem wielkości gradientu użytego do jednej aktualizacji wag?

---

## 17. Scheduler LR (harmonogram współczynnika uczenia)

Scheduler zmienia learning rate w trakcie treningu według ustalonej reguły — np. `cosine` (gładkie zmniejszanie wg krzywej kosinusoidalnej) albo `reduce_on_plateau` (zmniejsz, gdy monitorowana metryka przestaje się poprawiać). Te dwa typy schedulerów w PyTorch mają niezgodne sygnatury `.step()` — `ReduceLROnPlateau.step(metric)` przyjmuje wartość metryki, `CosineAnnealingLR.step()` nie przyjmuje nic.

**Gdzie w repo**: `medrisk_ml/training/scheduler.py::SchedulerWrapper` ujednolica to za jednym interfejsem `.step(metric=None)`.

```python
def step(self, metric: float | None = None) -> None:
    if self.scheduler is None:
        return
    if self.name == "reduce_on_plateau":
        if metric is None:
            raise ValueError("reduce_on_plateau requires a metric value on step()")
        self.scheduler.step(metric)
    else:
        self.scheduler.step()
```

**Częsty błąd początkującego**: wywołanie schedulera ze złą częstotliwością — np. raz na batch zamiast raz na epokę dla `CosineAnnealingLR`, którego `T_max` jest definiowane w epokach. To rozjeżdża zaplanowaną krzywą zmiany LR względem rzeczywistego czasu treningu.

**Pytanie rekrutacyjne**: Czemu pole `scheduler: Any` w `SchedulerWrapper` nie jest dokładniej typowane (np. `torch.optim.lr_scheduler.LRScheduler`), mimo że projekt ma mypy w trybie strict?

---

## 18. Warmup

Warmup to stopniowe *zwiększanie* learning rate od bardzo małej wartości do docelowej w pierwszych epokach/krokach treningu, zamiast zaczynać od razu z pełną wartością — stabilizuje wczesny trening, gdy wagi (zwłaszcza losowo zainicjalizowane) są najbardziej podatne na duże, destrukcyjne aktualizacje.

**Gdzie w repo**: `medrisk_ml/config.py::TrainingSection.warmup_epochs` (pole konfiguracyjne, walidowane jako `>= 0`) — `configs/ml/resnet18.yaml` ustawia `warmup_epochs: 1`.

```yaml
training:
  scheduler: cosine
  warmup_epochs: 1
```

**Częsty błąd początkującego**: ustawianie warmupu dla bardzo krótkich, syntetycznych eksperymentów smoke-testowych (`configs/ml/smoke.yaml` ma `warmup_epochs: 0`) — przy 2 epokach treningu warmup zająłby większość albo cały budżet treningowy, nie dając modelowi czasu na nic poza "rozgrzewką".

**Pytanie rekrutacyjne**: Czemu `configs/ml/smoke.yaml` celowo ustawia `warmup_epochs: 0`, podczas gdy `configs/ml/resnet18.yaml` ustawia `1`?

---

## 19. Mixed precision (AMP — Automatic Mixed Precision)

Mixed precision liczy część operacji w treningu (głównie forward/backward) w mniejszej precyzji (float16) zamiast standardowej float32 — szybciej i z mniejszym zużyciem pamięci GPU, przy zachowaniu float32 tam, gdzie precyzja jest krytyczna (np. akumulacja gradientów), dzięki `GradScaler`, który skaluje stratę, by uniknąć zaniku gradientu w float16.

**Gdzie w repo**: `medrisk_ml/training/engine.py::train_one_epoch` — i `ResolvedDevice.supports_amp`, które blokuje AMP na CPU/MPS (CUDA AMP nie ma tam sensu/wsparcia w tym kodzie).

```python
amp_enabled = mixed_precision and device.supports_amp
scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)
...
autocast_ctx = torch.autocast(device_type="cuda") if amp_enabled else contextlib.nullcontext()
with autocast_ctx:
    logits = _forward_logits(model, images)
```

**Częsty błąd początkującego**: ustawienie `mixed_precision: true` w configu i zdziwienie, że "nic się nie zmienia" na CPU. AMP w tym projekcie jest jawnie ograniczone do CUDA — `supports_amp` zwraca `False` dla CPU/MPS, więc flaga jest po prostu ignorowana, nie powoduje błędu.

**Pytanie rekrutacyjne**: Co dokładnie robi `GradScaler`, i czemu jest potrzebny *dodatkowo* do samego liczenia operacji w float16 (czyli — jaki konkretny problem numeryczny rozwiązuje skalowanie straty)?

---

## 20. Overfitting (przeuczenie) i underfitting (niedouczenie)

Przeuczenie: model uczy się "na pamięć" szczegółów zbioru treningowego (łącznie z szumem), więc świetnie radzi sobie na `train`, ale gorzej na `val`/`test` — strata walidacyjna zaczyna rosnąć, mimo że treningowa wciąż spada. Niedouczenie: model jest zbyt prosty albo trenowany zbyt krótko, żeby nauczyć się nawet wzorców ze zbioru treningowego.

**Gdzie w repo**: `medrisk_ml/training/trainer.py::fit` zapisuje `train_loss` i `val_loss` per epoka właśnie po to, by tę rozbieżność było widać w `training_history.csv`; `EarlyStopping` (punkt 38) automatycznie reaguje na przeuczenie, zatrzymując trening, gdy walidacja przestaje się poprawiać.

```python
epoch_record: dict[str, Any] = {
    "epoch": epoch,
    "train_loss": train_result.loss,
    "val_loss": val_result.loss,
    ...
}
```

**Częsty błąd początkującego**: ocena modelu tylko na podstawie straty/metryki treningowej. Niska strata treningowa przy wysokiej stracie walidacyjnej to *podręcznikowy* sygnał przeuczenia, nie sukcesu.

**Pytanie rekrutacyjne**: Po 10 epokach `train_loss` spada konsekwentnie, a `val_loss` spada do epoki 4, a potem zaczyna rosnąć. Który checkpoint zapisze `EarlyStopping` jako "best", i czemu nie checkpoint z epoki 10?

---

## 21. Dropout

Dropout losowo "wygasza" (zeruje) część neuronów podczas treningu (z prawdopodobieństwem `p`), zmuszając sieć, by nie polegała nadmiernie na pojedynczych neuronach — działa tylko w trakcie treningu (`model.train()`); w trakcie ewaluacji (`model.eval()`) jest wyłączony, a wagi są odpowiednio przeskalowane.

**Gdzie w repo**: `medrisk_ml/models/baseline_cnn.py::BaselineCNN.classifier` i `medrisk_ml/models/resnet.py::build_resnet18` (dropout przed finalną warstwą liniową w obu architekturach).

```python
self.classifier = nn.Sequential(
    nn.Flatten(),
    nn.Dropout(self.config.dropout),
    nn.Linear(256, 1),
)
```

**Częsty błąd początkującego**: zapominanie o wywołaniu `model.eval()` przed ewaluacją/inferencją. Dropout (i BatchNorm — punkt 24) zachowują się różnie w trybie `train()` i `eval()` — ewaluacja w trybie `train()` doda niepotrzebny, niedeterministyczny szum do wyników.

**Pytanie rekrutacyjne**: `medrisk_ml/explainability/gradcam.py::GradCAM.generate` jawnie przełącza model w `eval()` na czas liczenia mapy, a potem *przywraca* poprzedni stan (`was_training`). Czemu to przywracanie jest ważne, a nie tylko samo przełączenie na `eval()`?

---

## 22. Augmentacja danych

Augmentacja danych to losowe, etykieto-zachowujące przekształcenia obrazu treningowego (odbicia, obroty, lekkie przesunięcia, jitter kolorów) — sztucznie zwiększa różnorodność danych treningowych i zmniejsza przeuczenie. Stosowana *tylko* na zbiorze treningowym — `val`/`test`/inferencja muszą być deterministyczne.

**Gdzie w repo**: `medrisk_ml/data/transforms.py::build_transform`.

```python
if split == "train":
    ops += [
        T.RandomHorizontalFlip(p=0.5),
        T.RandomVerticalFlip(p=0.5),
        _rotate90_choice(),
        T.RandomAffine(degrees=0, translate=(0.05, 0.05), scale=(0.95, 1.05)),
        T.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0.02),
    ]
```

**Częsty błąd początkującego**: stosowanie zbyt agresywnej augmentacji (duże ścinanie/shear, ekstremalne zmiany koloru) na obrazach histopatologicznych — może zniszczyć morfologię tkanki, czyli właśnie to, czego model ma się nauczyć. Stąd w tym projekcie tylko odbicia/obroty (płatki tkanki nie mają "góry") i łagodny jitter.

**Pytanie rekrutacyjne**: Czemu odbicia (flip) i obroty o 90° są uznane za bezpieczne (etykieto-zachowujące) dla łatek PCam, a np. duże losowe przycięcie środka obrazu — nie byłoby?

---

## 23. Normalizacja danych (mean/std)

Normalizacja przeskalowuje wartości pikseli tak, by miały (w przybliżeniu) średnią 0 i odchylenie standardowe 1 — sieci neuronowe trenują się stabilniej i szybciej na danych w tej skali niż na surowych wartościach `[0, 255]` lub `[0, 1]`.

**Gdzie w repo**: `medrisk_ml/data/statistics.py::compute_normalization_stats` (liczone **tylko** z `train`, patrz punkt 6) dla `baseline_cnn`; dla `resnet18` używane są stałe, znane z góry statystyki ImageNet (`medrisk_ml/constants.py::IMAGENET_MEAN/STD`) — bo to są statystyki, na których backbone był pretrenowany, więc zmiana ich zepsułaby przeniesione cechy.

```python
def _normalization_for(architecture, mean, std):
    if architecture == "resnet18":
        return T.Normalize(mean=list(IMAGENET_MEAN), std=list(IMAGENET_STD))
    if mean is None or std is None:
        raise ValueError("baseline_cnn normalization requires train-set mean/std from ...")
    return T.Normalize(mean=list(mean), std=list(std))
```

**Częsty błąd początkującego**: użycie statystyk ImageNet dla modelu trenowanego od zera (`baseline_cnn`), albo odwrotnie — policzenie własnych statystyk dla pretrenowanego `resnet18`. Oba błędy są "ciche" (kod się wykona), ale degradują jakość modelu w sposób trudny do zdiagnozowania bez znajomości tej zasady.

**Pytanie rekrutacyjne**: Dlaczego normalizacja dla `resnet18` jest "udokumentowana, nie obliczona" (cytat z kodu), a dla `baseline_cnn` — obliczona?

---

## 24. BatchNorm (normalizacja wsadowa)

`BatchNorm2d` normalizuje aktywacje *wewnątrz* sieci (nie na wejściu, jak punkt 23) na podstawie statystyk bieżącego batcha podczas treningu, a podczas ewaluacji — na podstawie zgromadzonej w treningu średniej ruchomej. Stabilizuje i przyspiesza trening głębokich sieci.

**Gdzie w repo**: `medrisk_ml/models/baseline_cnn.py::_conv_block`.

```python
def _conv_block(in_channels: int, out_channels: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
        nn.BatchNorm2d(out_channels),
        nn.ReLU(inplace=True),
        nn.MaxPool2d(kernel_size=2),
    )
```

**Częsty błąd początkującego**: trenowanie z bardzo małym `batch_size` (np. 1-2) przy `BatchNorm` — statystyki pojedynczego mikro-batcha są zbyt szumne, żeby normalizacja miała sens, co psuje trening w sposób trudny do zdiagnozowania bez znajomości tej zależności.

**Pytanie rekrutacyjne**: Czemu `BatchNorm` zachowuje się różnie w `model.train()` vs `model.eval()` (tak jak Dropout, punkt 21), i co konkretnie się zmienia?

---

## 25. Warstwa konwolucyjna (Conv2d)

Warstwa konwolucyjna przesuwa mały, uczony filtr (kernel) po obrazie, licząc w każdym miejscu sumę ważoną lokalnego sąsiedztwa pikseli — wykrywa lokalne wzorce (krawędzie, tekstury), niezależnie od tego, *gdzie* na obrazie się znajdują (invariancja translacyjna).

**Gdzie w repo**: `medrisk_ml/models/baseline_cnn.py::_conv_block` — `nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1)`.

```python
nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1)
```

`padding=1` z `kernel_size=3` zachowuje rozmiar przestrzenny wejścia (wysokość/szerokość się nie zmieniają na tej warstwie) — zmienia się tylko liczba kanałów.

**Częsty błąd początkującego**: mylenie liczby kanałów wejściowych/wyjściowych z rozmiarem przestrzennym obrazu. `Conv2d(32, 64, ...)` oznacza "32 kanały wejściowe → 64 kanałów wyjściowych", i nie mówi nic samo z siebie o tym, czy obraz się zmniejszy (to robi `stride`/`padding`/`MaxPool2d`, patrz punkt 26).

**Pytanie rekrutacyjne**: Ile parametrów (wag) ma jedna warstwa `nn.Conv2d(32, 64, kernel_size=3)` (bez biasu liczonego osobno)? Jak to się skaluje względem rozmiaru obrazu wejściowego?

---

## 26. Pooling (MaxPool)

Pooling redukuje rozmiar przestrzenny mapy aktywacji, biorąc np. maksimum (`MaxPool2d`) z lokalnych okien — zmniejsza koszt obliczeniowy kolejnych warstw i wprowadza niewielką odporność na drobne przesunięcia obiektu na obrazie.

**Gdzie w repo**: `medrisk_ml/models/baseline_cnn.py::_conv_block` — `nn.MaxPool2d(kernel_size=2)` na końcu każdego z 4 bloków, czyli obraz wejściowy 96×96 jest po czterech blokach zmniejszony do 6×6 (`96 / 2**4 = 6`).

```python
nn.MaxPool2d(kernel_size=2)
```

**Częsty błąd początkującego**: zakładanie, że pooling "uczy się" czegokolwiek — to operacja deterministyczna, bez wag. To, co się uczy w danym bloku, to filtry konwolucyjne *przed* poolingiem.

**Pytanie rekrutacyjne**: Po czterech blokach `_conv_block` (każdy z `MaxPool2d(kernel_size=2)`), jaki jest rozmiar przestrzenny mapy aktywacji dla obrazu wejściowego 96×96? A dla 64×64 (jak w `tests/ml/test_gradcam.py`)?

---

## 27. Global Average Pooling (GAP)

Global Average Pooling redukuje całą mapę aktywacji `(C, H, W)` do jednego wektora `(C,)`, biorąc średnią po wszystkich pozycjach przestrzennych każdego kanału — pozwala sieci akceptować obrazy o różnych rozmiarach wejściowych i drastycznie redukuje liczbę parametrów w porównaniu do "spłaszczenia" (`Flatten`) i dużej warstwy liniowej.

**Gdzie w repo**: `medrisk_ml/models/baseline_cnn.py::BaselineCNN.pool` — `nn.AdaptiveAvgPool2d(1)`, zastosowane po ostatnim bloku konwolucyjnym, tuż przed klasyfikatorem.

```python
self.pool = nn.AdaptiveAvgPool2d(1)
```

**Częsty błąd początkującego**: użycie `nn.Flatten()` od razu po warstwach konwolucyjnych, bez GAP — dla mapy `(256, 6, 6)` to dałoby wektor `9216`-elementowy wejściowy do warstwy liniowej, czyli 9× więcej parametrów niż wektor `256`-elementowy po GAP, bez gwarancji lepszej jakości.

**Pytanie rekrutacyjne**: Co dokładnie robi `nn.AdaptiveAvgPool2d(1)` z tensorem o kształcie `(B, 256, 6, 6)` — jaki jest kształt wyniku?

---

## 28. CNN od zera (baseline architecture)

"CNN od zera" oznacza sieć konwolucyjną z losowo zainicjalizowanymi wagami, trenowaną wyłącznie na danych tego projektu — bez korzystania z wag wyuczonych na innym zbiorze danych (w przeciwieństwie do transfer learning, punkt 29).

**Gdzie w repo**: `medrisk_ml/models/baseline_cnn.py::BaselineCNN` — cztery bloki Conv-BatchNorm-ReLU-MaxPool podwajające liczbę kanałów (32→64→128→256), GAP, dropout, jedna warstwa liniowa do jednego logitu. Architektura zaprojektowana tak, by była "prosta do wyjaśnienia na rozmowie juniorskiej" (cytat z docstringa modułu).

```python
self.features = nn.Sequential(
    _conv_block(channels, 32),
    _conv_block(32, 64),
    _conv_block(64, 128),
    _conv_block(128, 256),
)
```

**Częsty błąd początkującego**: oczekiwanie, że mały CNN od zera dorówna pretrenowanemu ResNet18 na tej samej, ograniczonej liczbie epok/danych. Sieć od zera musi nauczyć się *wszystkiego* (łącznie z podstawowymi detektorami krawędzi) tylko z dostępnych danych — pretrenowany backbone już to ma.

**Pytanie rekrutacyjne**: Jaką rolę odgrywa `BaselineCNNConfig` (dataclass) w stosunku do samej klasy `BaselineCNN` — czemu konfiguracja i model są rozdzielone na dwie klasy?

---

## 29. Transfer learning

Transfer learning to wykorzystanie sieci wytrenowanej na jednym, dużym zbiorze danych (np. ImageNet — miliony zdjęć, tysiące kategorii) jako punktu startowego dla innego zadania (tu: klasyfikacja histopatologiczna) — niskopoziomowe cechy (krawędzie, tekstury, kształty) wyuczone na ogólnych obrazach często przenoszą się na zupełnie inną domenę.

**Gdzie w repo**: `medrisk_ml/models/resnet.py::build_resnet18` — ładuje wagi `ResNet18_Weights.DEFAULT` (pretrenowane na ImageNet) i zamienia tylko ostatnią warstwę (`fc`) na nową, losowo zainicjalizowaną, jedno-logitową głowicę.

```python
weights = ResNet18_Weights.DEFAULT if pretrained else None
model = resnet18(weights=weights)
in_features = model.fc.in_features
model.fc = nn.Sequential(nn.Dropout(dropout), nn.Linear(in_features, 1))
```

**Częsty błąd początkującego**: zapominanie, że nowa głowica (`fc`) startuje *losowo* zainicjalizowana, nawet gdy `pretrained=True` — "pretrenowany" odnosi się tylko do backbone'u, nie do nowo dodanej warstwy klasyfikującej, która musi się nauczyć od zera.

**Pytanie rekrutacyjne**: Czemu obrazy histopatologiczne (zupełnie inna domena niż zdjęcia z ImageNet — psy, samochody, krajobrazy) mogą w ogóle skorzystać z cech wyuczonych na ImageNet?

---

## 30. Pretrained backbone i wagi ImageNet

"Backbone" to część sieci odpowiedzialna za ekstrakcję cech (tu: wszystko w ResNet18 poza ostatnią warstwą `fc`). "Pretrained" oznacza, że jego wagi nie są losowe na starcie, a pochodzą z wcześniejszego treningu na ImageNet — stąd normalizacja wejścia musi używać tych samych statystyk, na których ten trening się odbył (punkt 23).

**Gdzie w repo**: `medrisk_ml/config.py::ModelSection` — `pretrained: bool`, z walidacją wymuszającą `pretrained=False` dla `baseline_cnn` (bo ta architektura nie ma żadnych pretrenowanych wag do załadowania).

```python
@model_validator(mode="after")
def _architecture_consistency(self) -> ModelSection:
    if self.architecture == "baseline_cnn" and self.pretrained:
        raise ValueError(
            "model.pretrained=true is not supported for architecture='baseline_cnn'"
        )
    return self
```

**Częsty błąd początkującego**: traktowanie "pretrained" jako gwarancji lepszego wyniku w każdej sytuacji. Dla bardzo specyficznej domeny (np. obrazy mikroskopowe znacznie różniące się od naturalnych zdjęć) korzyść z transferu bywa mniejsza niż dla domen bliższych ImageNet — to wciąż empiryczne pytanie, nie aksjomat.

**Pytanie rekrutacyjne**: Co konkretnie zawiera `ResNet18_Weights.DEFAULT` — tylko wagi, czy też metadane (np. dokładne statystyki normalizacji, na których model był trenowany)? Sprawdź dokumentację torchvision.

---

## 31. Freezing / unfreezing warstw

"Zamrożenie" warstwy (`param.requires_grad = False`) wyklucza jej wagi z aktualizacji przez optimizer — gradient wciąż może przez nią płynąć (do warstw wcześniejszych), ale jej własne wagi się nie zmieniają. "Odmrożenie" odwraca to.

**Gdzie w repo**: `medrisk_ml/models/resnet.py::build_resnet18` — `freeze_backbone=True` zamraża wszystko poza `fc.*`; `unfreeze_from_layer` selektywnie odmraża od podanej warstwy w głąb, według ustalonej kolejności `_UNFREEZE_ORDER`.

```python
_UNFREEZE_ORDER = ("conv1", "bn1", "layer1", "layer2", "layer3", "layer4", "fc")
...
if freeze_backbone:
    for name, param in model.named_parameters():
        param.requires_grad = name.startswith("fc.")
```

**Częsty błąd początkującego**: zapominanie, że zamrożenie wag nie zwalnia automatycznie pamięci/czasu obliczeń na forward pass przez te warstwy — wciąż trzeba przez nie przepuścić dane, zamrożenie oszczędza tylko backward/aktualizację tych konkretnych wag.

**Pytanie rekrutacyjne**: Jeśli zapomnisz przefiltrować `model.parameters()` po `requires_grad=True` przy budowaniu optimizera (punkt 12), a backbone jest zamrożony — czy trening się wywali, czy po prostu zadzieje się coś niepotrzebnego (i co)?

---

## 32. Fine-tuning etapowy (staged) i catastrophic forgetting

Catastrophic forgetting to utrata wcześniej wyuczonych, użytecznych cech, gdy pretrenowane wagi są zbyt agresywnie aktualizowane (zbyt wysoki learning rate, zbyt wczesne odmrożenie) na nowym, małym zbiorze danych. Fine-tuning etapowy minimalizuje to ryzyko: najpierw trenuje się tylko nową głowicę (Stage A, backbone zamrożony), a potem, opcjonalnie i ręcznie, odmraża się część backbone'u z dużo niższym learning rate (Stage B).

**Gdzie w repo**: `configs/ml/resnet18.yaml` (Stage A) + komentarz dokumentujący dokładną komendę dla Stage B; pełne uzasadnienie w [docs/experiment-protocol.md](../experiment-protocol.md).

```yaml
# Not auto-executed. For Stage B fine-tuning, re-run with overrides, e.g.:
#   --set model.freeze_backbone=false --set model.unfreeze_from_layer=layer4 \
#   --set training.learning_rate=0.00005
```

**Częsty błąd początkującego**: odmrażanie *całego* backbone'u od razu, z tym samym learning rate co głowica. To właśnie prosi się o catastrophic forgetting — stąd `unfreeze_from_layer` pozwala odmrozić tylko najgłębsze (najbardziej zadaniowo-specyficzne) warstwy, zostawiając wczesne, bardziej "ogólne" warstwy (np. `conv1`) zamrożone.

**Pytanie rekrutacyjne**: Czemu żaden z dwóch etapów (Stage A/B) nie jest automatycznie łączony w jedno wywołanie CLI — co to mówi o tym, jak ten projekt traktuje uruchamianie treningu na prawdziwych danych?

---

## 33. Seed (ziarno) i determinizm

Seed inicjalizuje generator liczb pseudolosowych — z tym samym seedem te same operacje "losowe" (inicjalizacja wag, augmentacja, tasowanie batchy) dają identyczny wynik przy każdym uruchomieniu. Determinizm to dodatkowe wymuszenie, by *wszystkie* operacje (łącznie z niektórymi nieddeterministycznymi z natury kernelami CUDA) były powtarzalne — kosztem wydajności.

**Gdzie w repo**: `medrisk_ml/utils/reproducibility.py::set_seed`; dane syntetyczne idą dalej — każda próbka jest generowana z `np.random.default_rng([seed, split_offset, index])`, **nigdy** z wbudowanego `hash()` Pythona, bo `hash()` na tuplach/stringach jest losowo "solony" per-proces przez `PYTHONHASHSEED` i nie jest stabilny między uruchomieniami.

```python
def set_seed(seed: int, deterministic: bool = False) -> ReproducibilityReport:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        torch.use_deterministic_algorithms(True)
        ...
```

**Częsty błąd początkującego**: zakładanie, że ten sam seed gwarantuje identyczne wyniki bitowe na *różnym* sprzęcie (np. innej karcie GPU) albo z inną wersją CUDA/cuDNN. `ReproducibilityReport` jawnie to dokumentuje jako niegarantowane — seed gwarantuje powtarzalność na tej samej maszynie z tymi samymi wersjami bibliotek.

**Pytanie rekrutacyjne**: Czemu `runtime.deterministic=true` i `runtime.benchmark=true` nie mogą być ustawione jednocześnie w configu (sprawdź `RuntimeSection._deterministic_benchmark_conflict`)?

---

## 34. Device (CPU / GPU / CUDA / MPS)

"Device" to fizyczne miejsce, gdzie tensor żyje i gdzie wykonywane są na nim obliczenia — CPU (zawsze dostępne, wolniejsze dla sieci neuronowych), CUDA (GPU NVIDIA), MPS (GPU Apple Silicon). Tensor i model muszą być na tym samym device, inaczej operacja się wywali.

**Gdzie w repo**: `medrisk_ml/utils/device.py::resolve_device` — `"auto"` wybiera najlepsze dostępne (CUDA → MPS → CPU) bez pytania; jawne żądanie niedostępnego backendu (np. `"cuda"` na maszynie bez GPU) rzuca błąd, *nie* tworzy cichego fallbacku.

```python
if requested == "cuda":
    if not torch.cuda.is_available():
        raise DeviceUnavailableError(
            "CUDA was explicitly requested but torch.cuda.is_available() is False."
        )
    return _build("cuda", requested)
```

**Częsty błąd początkującego**: przenoszenie modelu na GPU (`model.to(device)`), ale zapominanie o przeniesieniu danych wejściowych (albo odwrotnie). PyTorch nie przenosi ich automatycznie za siebie — błąd `Expected all tensors to be on the same device` jest jednym z najczęstszych błędów na starcie z PyTorch.

**Pytanie rekrutacyjne**: Czemu żądanie `"auto"` *nigdy* nie rzuca `DeviceUnavailableError`, a jawne żądanie `"cuda"`/`"mps"` — może? Co to mówi o filozofii tego API (jawność vs wygoda)?

---

## 35. DataLoader i workery (worker processes)

`DataLoader` opakowuje `Dataset` i dostarcza dane w batchach, opcjonalnie równolegle w wielu procesach (`num_workers > 0`) — wczytywanie/przetwarzanie obrazu z dysku może być wolniejsze niż sam krok GPU, więc workery przygotowują kolejne batche w tle, podczas gdy GPU liczy obecny.

**Gdzie w repo**: `medrisk_ml/data/loaders.py::build_loader` — `shuffle=True` tylko dla `train`; `worker_init_fn=seed_worker` zapewnia, że każdy worker ma inny, ale deterministyczny seed (inaczej wszystkie workery losowałyby identycznie, co skutkowałoby duplikatami augmentacji).

```python
if num_workers > 0:
    kwargs["worker_init_fn"] = seed_worker
    kwargs["persistent_workers"] = persistent_workers
```

**Częsty błąd początkującego**: tasowanie (`shuffle=True`) zbiorów walidacyjnego/testowego. Numerycznie nic by się nie zepsuło, ale eksport predykcji per-próbka (do CSV, do error analysis) staje się trudniejszy do debugowania/porównania między uruchomieniami — stąd ten projekt świadomie nigdy nie tasuje `val`/`test`.

**Pytanie rekrutacyjne**: Dlaczego `build_loader` rzuca błąd, gdy `persistent_workers=True` jest ustawione razem z `num_workers=0`, zamiast po prostu zignorować tę flagę?

---

## 36. Dataset (klasa `torch.utils.data.Dataset`)

`Dataset` to interfejs z dwiema metodami: `__len__` (ile próbek) i `__getitem__` (jak wczytać/zwrócić próbkę o danym indeksie) — `DataLoader` (punkt 35) wie, jak z niego korzystać, bez znajomości szczegółów konkretnego zbioru danych.

**Gdzie w repo**: dwie implementacje współdzielące ten sam kontrakt zwracanej wartości `(tensor, label, sample_id)`: `medrisk_ml/data/synthetic.py::SyntheticHistopathologyDataset` i `medrisk_ml/data/datasets.py::PCamDataset` (adapter na `torchvision.datasets.PCAM`).

```python
def __getitem__(self, index: int) -> tuple[torch.Tensor, int, str]:
    image, label = self._dataset[index]
    sample_id = f"pcam_{self.split}_{index:06d}"
    return image, int(label), sample_id
```

**Częsty błąd początkującego**: zakładanie, że dwa różne `Dataset`y muszą mieć identyczną *implementację*, żeby działały z resztą pipeline'u. Wystarczy identyczny *kontrakt* (te same typy zwracane z `__getitem__`) — dzięki temu trening/ewaluacja/Grad-CAM nie muszą wiedzieć, czy dane są syntetyczne czy prawdziwe.

**Pytanie rekrutacyjne**: Czemu `sample_id` jest stringiem zawierającym split i indeks (np. `"pcam_test_000042"`), a nie samym integerem? Jak to jest wykorzystywane w `medrisk_ml/cli.py::_index_from_sample_id`?

---

## 37. Checkpoint

Checkpoint to zapis stanu modelu (i opcjonalnie optimizera/schedulera) na dysku w danym momencie treningu — pozwala wznowić trening, porównać epoki, albo wczytać konkretny, najlepszy moment do ewaluacji/inferencji bez retrenowania.

**Gdzie w repo**: `medrisk_ml/training/checkpointing.py` — checkpoint to nie tylko wagi, ale też metadane potrzebne do audytu: architektura, configi, nazwy klas, normalizacja, próg, kalibracja, commit git, znacznik czasu. Wczytywanie zawsze z `weights_only=True` (ograniczony unpickler PyTorch) — bezpieczne, bo payload zawiera tylko tensory/proste typy, nigdy niestandardowe klasy.

```python
raw: dict[str, Any] = torch.load(path, map_location=map_location, weights_only=True)
missing = [key for key in _REQUIRED_KEYS if key not in raw]
if missing:
    raise CheckpointError(f"Checkpoint {path} is missing required field(s): {missing}")
```

**Częsty błąd początkującego**: zapisywanie checkpointu jako gołego `model.state_dict()` bez żadnych metadanych. Pół roku później nikt (łącznie z autorem) nie będzie pamiętał, jaka architektura/konfiguracja/normalizacja odpowiada temu plikowi — stąd `CheckpointPayload` wymusza komplet metadanych przy każdym zapisie.

**Pytanie rekrutacyjne**: Czemu `load_checkpoint` używa `weights_only=True` zamiast domyślnego (pełnego) odpicklowania, i jakie realne ryzyko bezpieczeństwa to ogranicza?

---

## 38. Early stopping

Early stopping zatrzymuje trening, gdy monitorowana metryka walidacyjna nie poprawia się przez `patience` epok pod rząd — zapobiega dalszemu (bezsensownemu, czasem szkodliwemu — patrz przeuczenie, punkt 20) trenowaniu po tym, jak model już "nauczył się tyle, ile mógł" na tych danych.

**Gdzie w repo**: `medrisk_ml/training/early_stopping.py::EarlyStopping` — operuje *wyłącznie* na wartościach z walidacji, nigdy z testu (patrz [docs/experiment-protocol.md](../experiment-protocol.md)).

```python
def step(self, value: float, epoch: int) -> bool:
    if self._is_improvement(value):
        self.best_value = value
        self.best_epoch = epoch
        self.counter = 0
    else:
        self.counter += 1
        if self.counter >= self.patience:
            self.should_stop = True
    return self.should_stop
```

**Częsty błąd początkującego**: mylenie "best checkpoint" z "checkpoint z ostatniej epoki przed zatrzymaniem". `best.pt` to checkpoint z epoki o najlepszej dotąd wartości metryki (`early_stopping.best_epoch`), nie z epoki, w której trening faktycznie się zatrzymał (`patience` epok później).

**Pytanie rekrutacyjne**: `patience=5`, a najlepszy wynik był w epoce 10. W której epoce trening faktycznie się zatrzyma (zakładając brak dalszej poprawy)?

---

## 39. Konfiguracja eksperymentu i walidacja (pydantic)

Konfiguracja eksperymentu to jeden, kompletny opis "co trenować i jak" — w tym projekcie jeden plik YAML, walidowany w całości przed jakimkolwiek użyciem, z `extra="forbid"` na każdej sekcji, czyli nieznane pole (literówka) to twardy błąd, nie cichy no-op.

**Gdzie w repo**: `medrisk_ml/config.py::ExperimentConfig` (sekcje: `experiment`, `data`, `model`, `training`, `evaluation`, `logging`, `runtime`); pełny opis w [docs/ml-architecture.md](../ml-architecture.md).

```python
class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
```

**Częsty błąd początkującego**: traktowanie YAML configu jako "po prostu danych", bez sprawdzania, czy walidacja faktycznie się uruchomiła. W tym projekcie *nie da się* tego pominąć — `load_config()` zawsze przepuszcza wynik przez `ExperimentConfig.model_validate(...)`, więc błąd w configu (np. `training.epochs: -5`) jest wykryty zanim jakikolwiek kod treningowy się uruchomi, nie w połowie treningu.

**Pytanie rekrutacyjne**: Co się stanie, jeśli w YAML configu napiszesz `trainnig.epochs: 5` (literówka w nazwie sekcji)? Czy ten projekt to wykryje, i jak?

---

## 40. CLI (interfejs linii komend) i argparse

CLI (Command-Line Interface) to sposób uruchamiania programu z terminala z parametrami — `argparse` (biblioteka standardowa Pythona) parsuje te parametry do obiektu z atrybutami, z automatyczną walidacją typów i generowaniem `--help`.

**Gdzie w repo**: `medrisk_ml/cli.py::build_parser` — subkomendy `environment`, `data inspect`, `data download`, `train`, `evaluate`, `explain`, `register`, `verify-bundle`, każda ze swoimi argumentami.

```python
train_parser = subparsers.add_parser("train", help="Train a model from a config")
_add_config_args(train_parser)
train_parser.add_argument("--progress", action="store_true", help="Show tqdm progress bars")
train_parser.set_defaults(func=cmd_train)
```

**Częsty błąd początkującego**: pisanie logiki biznesowej (budowanie datasetów, trenowanie) prosto w funkcji obsługującej argumenty CLI. Tutaj `cmd_train` *woła* funkcje z `data/`, `models/`, `training/` — CLI jest "tylko" warstwą parsowania argumentów i orkiestracji, identycznie jak warstwa `api/` w Fazie 1 nie zawiera logiki biznesowej.

**Pytanie rekrutacyjne**: Jak `--set training.epochs=2` trafia do finalnego, zwalidowanego configu — w jakiej kolejności względem wczytania samego pliku YAML jest stosowane (sprawdź `load_config`)?

---

## 41. Próg decyzyjny (threshold)

Model zwraca prawdopodobieństwo (liczbę w `[0, 1]`) — próg decyzyjny zamienia tę liczbę na konkretną etykietę `0`/`1` (`prob >= threshold → positive`). Domyślny próg `0.5` nie jest żadną świętością — bywa nieoptymalny, zwłaszcza przy niezbalansowanych klasach albo różnych kosztach błędów (fałszywy alarm vs przeoczenie).

**Gdzie w repo**: `medrisk_ml/evaluation/thresholding.py::select_threshold`, zawsze dopasowywany na zbiorze `val` (punkt 47). Cztery strategie: `fixed`, `youden_j`, `max_f1`, `target_sensitivity` — pełny opis w [docs/experiment-protocol.md](../experiment-protocol.md).

```python
y_pred = (prob_arr >= threshold).astype(int)
```

**Częsty błąd początkującego**: traktowanie `0.5` jako uniwersalnie "neutralnego" progu. Dla zadania, gdzie przeoczenie pozytywnego przypadku jest znacznie kosztowniejsze niż fałszywy alarm, niższy próg (większa czułość, niższa specyficzność) bywa właściwym wyborem — stąd strategia `target_sensitivity`.

**Pytanie rekrutacyjne**: Jeśli zmienisz próg z `0.5` na `0.3`, co się stanie z liczbą fałszywych pozytywów (FP) i fałszywych negatywów (FN) — w którą stronę pójdzie każda z nich?

---

## 42. Confusion matrix (macierz pomyłek) — TP/TN/FP/FN

Macierz pomyłek zestawia rzeczywistą etykietę z przewidzianą: TP (prawdziwie pozytywny — model powiedział "positive", i miał rację), TN (prawdziwie negatywny), FP (fałszywy alarm — model powiedział "positive", a było "negative"), FN (przeoczenie — model powiedział "negative", a było "positive").

**Gdzie w repo**: `medrisk_ml/evaluation/metrics.py::confusion_counts` i `ConfusionCounts`; wizualizacja: `medrisk_ml/evaluation/plots.py::plot_confusion_matrix`.

```python
tp = int(np.sum((true_arr == 1) & (pred_arr == 1)))
tn = int(np.sum((true_arr == 0) & (pred_arr == 0)))
fp = int(np.sum((true_arr == 0) & (pred_arr == 1)))
fn = int(np.sum((true_arr == 1) & (pred_arr == 0)))
```

**Częsty błąd początkującego**: mylenie FP i FN przy interpretacji wyniku w kontekście medycznym. FN (przeoczona tkanka nowotworowa) i FP (fałszywy alarm o tkance nowotworowej, gdy jej nie ma) mają zupełnie inne konsekwencje kliniczne — żaden pojedynczy "% poprawnych odpowiedzi" tego nie oddaje.

**Pytanie rekrutacyjne**: W diagnostyce nowotworowej, który błąd (FP czy FN) jest zwykle uznawany za "gorszy", i czemu (mimo że oba są błędami)?

---

## 43. Sensitivity, specificity, precision, recall, F1

Sensitivity (czułość, = recall) = TP/(TP+FN) — "z faktycznie chorych, ilu wykryliśmy". Specificity (specyficzność) = TN/(TN+FP) — "z faktycznie zdrowych, ilu poprawnie uznaliśmy za zdrowych". Precision (precyzja) = TP/(TP+FP) — "z tych, których uznaliśmy za chorych, ilu faktycznie było". F1 — harmoniczna średnia precision i recall, jedna liczba ważąca obie.

**Gdzie w repo**: `medrisk_ml/evaluation/metrics.py::compute_binary_metrics` — wszystkie liczone z tej samej macierzy pomyłek (punkt 42), przy ustalonym progu (punkt 41).

```python
sensitivity = _safe_div(counts.true_positive, counts.positive_count)
specificity = _safe_div(counts.true_negative, counts.negative_count)
precision = _safe_div(counts.true_positive, counts.true_positive + counts.false_positive)
```

**Częsty błąd początkującego**: patrzenie tylko na `accuracy` przy niezbalansowanych klasach. Model, który *zawsze* przewiduje "negative" na zbiorze, gdzie 95% próbek jest negatywnych, ma 95% accuracy i `sensitivity=0` — bezużyteczny, mimo wysokiej "trafności".

**Pytanie rekrutacyjne**: Dlaczego `compute_binary_metrics` zwraca `recall` jako po prostu alias na `sensitivity` (`recall = sensitivity`), a nie odrębne obliczenie? Czy te dwie metryki są w ogóle czymś innym w klasyfikacji binarnej?

---

## 44. ROC curve i ROC-AUC

Krzywa ROC (Receiver Operating Characteristic) wykreśla sensitivity (TPR) względem `1 - specificity` (FPR) dla *wszystkich* możliwych progów na raz. ROC-AUC (Area Under Curve) to pole pod tą krzywą — interpretowane jako "prawdopodobieństwo, że losowa próbka pozytywna dostanie wyższe prawdopodobieństwo niż losowa próbka negatywna." `AUC=0.5` to przypadek (losowe zgadywanie), `AUC=1.0` to perfekcyjne rozdzielenie klas.

**Gdzie w repo**: `medrisk_ml/evaluation/metrics.py::compute_binary_metrics` (`sklearn.metrics.roc_auc_score`); wykres: `medrisk_ml/evaluation/plots.py::plot_roc_curve` (pole liczone przez `sklearn.metrics.auc`, *nie* przez przestarzałe/usunięte w NumPy 2.x `np.trapz`).

```python
classes_present = np.unique(true_arr)
if classes_present.size < 2:
    roc_auc = float("nan")
else:
    roc_auc = float(roc_auc_score(true_arr, prob_arr))
```

**Częsty błąd początkującego**: liczenie ROC-AUC na zbiorze, gdzie obecna jest tylko jedna klasa (np. mały, niewyważony losowo batch). To matematycznie niezdefiniowane — stąd `nan`, nie `0.0` czy `1.0` (patrz [docs/evaluation.md](../evaluation.md), polityka niezdefiniowanych metryk).

**Pytanie rekrutacyjne**: Czemu ROC-AUC jest "niezmiennikiem względem progu" (nie potrzebuje ustalonego `threshold`), w odróżnieniu od `precision`/`recall`/`f1`?

---

## 45. PR curve i PR-AUC (precision-recall)

Krzywa precision-recall wykreśla precision względem recall dla wszystkich progów. PR-AUC (czasem zwane average precision) to pole pod tą krzywą — bardziej informatywne niż ROC-AUC, gdy klasy są silnie niezbalansowane (bo nie "rozmywa" rzadkiej klasy pozytywnej w mianowniku tak jak FPR w ROC).

**Gdzie w repo**: `medrisk_ml/evaluation/metrics.py::compute_binary_metrics` (`sklearn.metrics.average_precision_score`); wykres: `medrisk_ml/evaluation/plots.py::plot_pr_curve`.

```python
pr_auc = float(average_precision_score(true_arr, prob_arr))
```

**Częsty błąd początkującego**: używanie wyłącznie ROC-AUC do porównywania modeli na silnie niezbalansowanych danych medycznych (gdzie klasa pozytywna jest rzadka) — ROC-AUC może wyglądać "dobrze" nawet dla modelu słabego w wykrywaniu rzadkiej klasy, bo duża liczba prawdziwych negatywów dominuje obliczenie FPR.

**Pytanie rekrutacyjne**: Dwa modele mają identyczne ROC-AUC=0.9, ale różne PR-AUC (0.8 vs 0.5) na silnie niezbalansowanym zbiorze. Co to mówi o różnicy w ich praktycznej użyteczności?

---

## 46. Kalibracja (temperature scaling)

Model dobrze "rozróżniający" klasy (wysokie ROC-AUC) może być źle skalibrowany — np. systematycznie nadmiernie pewny swoich predykcji. Temperature scaling (Guo et al., 2017) uczy jednego skalara `T > 0`, przez który dzieli się logity przed sigmoidem, by skorygować tę pewność — dopasowywane na walidacji, bo dzielenie przez stałą dodatnią nie zmienia *rankingu* predykcji (więc ROC-AUC/PR-AUC są identyczne przed i po).

**Gdzie w repo**: `medrisk_ml/evaluation/calibration.py::fit_temperature` — optymalizacja w przestrzeni logarytmicznej (`log(T)`) przez LBFGS, co gwarantuje `T = exp(log_T) > 0` strukturalnie, bez dodatkowego ograniczenia w kodzie.

```python
def closure() -> torch.Tensor:
    optimizer.zero_grad()
    temperature = torch.exp(log_temperature)
    loss: torch.Tensor = loss_fn(logits_t / temperature, labels_t)
    loss.backward()
    return loss
```

**Częsty błąd początkującego**: oczekiwanie, że kalibracja "poprawi" ROC-AUC. Nie może — to matematyczna własność monotonicznego przekształcenia (dzielenie przez stałą dodatnią zachowuje porządek). Kalibracja poprawia tylko metryki czułe na *wartość* prawdopodobieństwa (Brier score, ECE — punkt 47), nie na sam ranking.

**Pytanie rekrutacyjne**: Czemu `fit_temperature` rzuca błąd (`CalibrationFittingError`), gdy etykiety walidacyjne zawierają tylko jedną klasę?

---

## 47. Brier score i Expected Calibration Error (ECE)

Brier score to średni kwadrat różnicy między przewidzianym prawdopodobieństwem a rzeczywistą etykietą (0 lub 1) — niższy = lepiej, i nagradza zarówno trafność, jak i pewność. ECE dzieli predykcje na biny wg przewidzianego prawdopodobieństwa i mierzy średnią (ważoną liczbą próbek w binie) różnicę między średnią pewnością a faktyczną dokładnością w każdym binie — "czy model, który mówi 80% pewności, faktycznie ma rację w ~80% takich przypadków?"

**Gdzie w repo**: `medrisk_ml/evaluation/metrics.py` (`brier_score`) i `medrisk_ml/evaluation/calibration.py::expected_calibration_error` + `reliability_diagram_bins` (dane do wykresu `calibration_curve.png`).

```python
ece += (count / n) * abs(bin_accuracy - bin_confidence)
```

**Częsty błąd początkującego**: traktowanie wysokiego ROC-AUC jako dowodu dobrej kalibracji. To dwie zupełnie różne właściwości modelu — model może świetnie *rozróżniać* klasy, ale być fatalnie skalibrowany (np. zawsze przewidywać 99% lub 1%, rzadko coś pomiędzy).

**Pytanie rekrutacyjne**: Model przewiduje zawsze albo `0.99`, albo `0.01` (nigdy wartości pomiędzy), i myli się w 10% przypadków. Czy taki model może mieć wysokie ROC-AUC i jednocześnie wysoki (zły) Brier score?

---

## 48. Bootstrap confidence interval (przedział ufności)

Bootstrap losuje (ze zwracaniem) wielokrotnie podzbiory tego samego rozmiaru z istniejącego zbioru testowego, liczy metrykę na każdym z nich, i bierze percentyle tego rozkładu jako przedział ufności — mówi, jak bardzo wynik mógłby się różnić, gdyby próbka testowa była "odrobinę inna" z tej samej populacji.

**Gdzie w repo**: `medrisk_ml/evaluation/evaluator.py::bootstrap_ci`.

```python
for _ in range(n_samples):
    indices = rng.integers(0, n, size=n)
    metrics = compute_binary_metrics(y_true[indices], y_prob[indices], threshold)
    value = metrics.get(metric_name)
    if isinstance(value, float) and not np.isnan(value):
        values.append(value)
```

**Częsty błąd początkującego**: interpretowanie wąskiego przedziału ufności jako dowodu, że model jest "solidny" w sensie klinicznym/wdrożeniowym. Bootstrap opisuje *tylko* niepewność próbkowania na tym jednym, ustalonym zbiorze testowym — różni skanerzy, szpitale, populacje pacjentów nie są w żaden sposób reprezentowane przez resampling tego samego zbioru (patrz [docs/evaluation.md](../evaluation.md)).

**Pytanie rekrutacyjne**: Czemu `bootstrap_ci` pomija (nie liczy do `values`) próbki bootstrapowe, dla których metryka wyszła `nan`, zamiast np. traktować je jako `0.0`?

---

## 49. Class imbalance (niezbalansowanie klas) i dlaczego niektóre metryki istnieją właśnie dlatego

Niezbalansowanie klas oznacza, że jedna klasa jest znacznie rzadsza niż druga — wtedy `accuracy` (punkt 43) i `roc_auc` (punkt 44) mogą wyglądać sztucznie dobrze, mimo że model radzi sobie źle z rzadką klasą. `balanced_accuracy` (średnia sensitivity i specificity) i `pr_auc` (punkt 45) są w tym projekcie obliczane właśnie jako odpowiedź na ten problem.

**Gdzie w repo**: `medrisk_ml/evaluation/metrics.py::compute_binary_metrics` liczy obie rodziny metryk razem, nigdy tylko `accuracy`/`roc_auc` w izolacji; `medrisk_ml/training/losses.py::build_loss` ma opcjonalny `pos_weight` właśnie na wypadek niezbalansowanego zbioru treningowego.

```python
balanced_accuracy = (
    float("nan")
    if np.isnan(sensitivity) or np.isnan(specificity)
    else (sensitivity + specificity) / 2.0
)
```

**Częsty błąd początkującego**: dodawanie `pos_weight` "na wszelki wypadek" nawet na danych już zbalansowanych (PCam jest ~50/50 — patrz [docs/dataset-card-pcam.md](../dataset-card-pcam.md)). To bez potrzeby zniekształca funkcję straty — `pos_weight` powinien wynikać z realnie zmierzonego niezbalansowania, nie z domyślnej "ostrożności".

**Pytanie rekrutacyjne**: Dlaczego `inspect_split()` (`medrisk_ml/data/metadata.py`) raportuje rzeczywisty rozkład klas per split, zamiast po prostu zakładać, że PCam jest zbalansowane "bo tak mówi dokumentacja"?

---

## 50. Error analysis (analiza błędów)

Analiza błędów wykracza poza zagregowane metryki i wyciąga *konkretne* przykłady warte ręcznego przeglądu: najpewniejsze fałszywe pozytywy/negatywy (model był pewny i się mylił), najmniej pewne poprawne predykcje (ledwo trafił), oraz przypadki blisko progu decyzyjnego (niewielka zmiana danych/modelu odwróciłaby decyzję).

**Gdzie w repo**: `medrisk_ml/evaluation/error_analysis.py` — pełny opis w [docs/evaluation.md](../evaluation.md).

```python
def highest_confidence_false_negatives(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    mask = (df["predicted_label"] == 0) & (df["true_label"] == 1)
    return df.loc[mask].sort_values("probability", ascending=True).head(top_n)
```

**Częsty błąd początkującego**: ograniczanie się do jednej zagregowanej liczby (np. "ROC-AUC=0.91, świetnie") bez przeglądnięcia choć kilku konkretnych błędów. Dwa modele z identycznym ROC-AUC mogą popełniać systematycznie inne, równie ważne błędy — agregat tego nie pokazuje.

**Pytanie rekrutacyjne**: Czemu `write_error_analysis` używa `df.to_string()` w blokach ```text```, a nie `df.to_markdown()`, mimo że markdown wyglądałby lepiej w renderowanym pliku `.md`?

---

## 51. Grad-CAM

Grad-CAM (Selvaraju et al., 2017) odpowiada na wąskie, konkretne pytanie: które miejsca w mapie aktywacji wybranej warstwy konwolucyjnej, gdyby były silniejsze, najbardziej zwiększyłyby (lub zmniejszyły) dany wynik modelu. Wynik to mapa ciepła (heatmap) nakładana na oryginalny obraz.

**Gdzie w repo**: `medrisk_ml/explainability/gradcam.py::GradCAM.generate` — implementacja od zera (bez zewnętrznej biblioteki Grad-CAM), żeby była w pełni audytowalna i przetestowana jednostkowo. Pełny opis i **obowiązkowy disclaimer**: [docs/explainability.md](../explainability.md).

```python
weights = gradients.mean(dim=(2, 3), keepdim=True)
weighted_combination = (weights * activations).sum(dim=1, keepdim=True)
heatmap = F.relu(weighted_combination)
```

**Częsty błąd początkującego**: traktowanie "gorącego" miejsca na mapie jako dowodu medycznego/biologicznego ("tu jest nowotwór"). Mapa pokazuje tylko, co było *wpływowe dla tego modelu w tej predykcji* — model może być wpływowo poprawny z niewłaściwego powodu (artefakt, a nie tkanka), i Grad-CAM to wiernie pokaże, bez ostrzeżenia, że powód jest błędny.

**Pytanie rekrutacyjne**: Model klasyfikacji binarnej ma tylko jeden logit wyjściowy — jak Grad-CAM "wybiera klasę", dla której liczy mapę, skoro nie ma (jak w klasyfikacji wieloklasowej) kilku logitów do wyboru?

---

## 52. Hook (forward/backward) w PyTorch

Hook to funkcja, którą rejestrujesz na module/tensorze, a PyTorch wywołuje ją automatycznie w odpowiednim momencie — forward hook po przejściu danych przez warstwę, backward hook (na tensorze) w momencie, gdy gradient przez niego przepływa. To mechanizm "podglądania" wnętrza sieci bez modyfikowania jej kodu.

**Gdzie w repo**: `medrisk_ml/explainability/hooks.py::ActivationsAndGradients` — forward hook na docelowej warstwie zapisuje aktywacje *i* rejestruje dodatkowy hook na samym tensorze wyjściowym, żeby przy `backward()` przechwycić jego gradient.

```python
def _save_activation(self, module, inputs, output):
    self.activations = output
    output.register_hook(self._save_gradient)

def _save_gradient(self, grad: torch.Tensor) -> None:
    self.gradients = grad
```

**Częsty błąd początkującego**: zapominanie o usunięciu hooków (`handle.remove()`) po użyciu. Niezwolniony hook zostaje zarejestrowany na module na zawsze (nawet po tym, jak obiekt `GradCAM` wyjdzie poza zasięg) — stąd `GradCAM` implementuje protokół `__enter__`/`__exit__` (`with GradCAM(...) as cam:`), żeby `release()` zawsze się wykonało.

**Pytanie rekrutacyjne**: Czemu `ActivationsAndGradients` używa hooka na *tensorze* (`output.register_hook`) zamiast `register_full_backward_hook` na samym module — jaki konkretny problem to rozwiązuje (sprawdź docstring `hooks.py`)?

---

## 53. Target layer i Class Activation Map

"Target layer" to konkretna warstwa konwolucyjna, której aktywacje/gradienty Grad-CAM wykorzystuje — zwykle ostatnia warstwa konwolucyjna przed głowicą klasyfikującą, bo ma już wysokopoziomowe, przestrzenne cechy, ale wciąż zachowuje rozdzielczość przestrzenną (w przeciwieństwie do warstw liniowych po `Flatten`/GAP).

**Gdzie w repo**: `medrisk_ml/models/factory.py::get_target_layer` — scentralizowane wybieranie warstwy per architektura, żeby żaden kod wołający nie musiał znać nazwy warstwy na pamięć.

```python
def get_target_layer(model: nn.Module, architecture: ArchitectureName) -> nn.Module:
    if architecture == "resnet18":
        target = model.layer4
    elif architecture == "baseline_cnn":
        target = model.features[-1]
    ...
```

**Częsty błąd początkującego**: hardkodowanie nazwy warstwy (np. `"layer4"`) w kodzie wołającym Grad-CAM, zamiast przez `get_target_layer`. Gdy ktoś dodałby trzecią architekturę, taki hardkodowany kod by się cicho zepsuł (zwrócił mapę z niewłaściwej warstwy) albo rzucił błąd atrybutu w niejasnym miejscu.

**Pytanie rekrutacyjne**: Czemu target layer dla `baseline_cnn` to `model.features[-1]` (ostatni blok), a nie np. `model.features[0]` (pierwszy blok)? Co różni informację dostępną w tych dwóch miejscach sieci?

---

## 54. Ograniczenia explainability (czego Grad-CAM NIE dowodzi)

Explainability (wyjaśnialność) w uczeniu maszynowym to próba uczynienia decyzji modelu zrozumiałą dla człowieka — Grad-CAM jest jedną z najpopularniejszych technik, ale ma istotne, dobrze znane ograniczenia, które trzeba świadomie komunikować, a nie zamiatać pod dywan.

**Gdzie w repo**: `medrisk_ml/constants.py::GRADCAM_DISCLAIMER`, wstrzykiwany do każdego katalogu z wygenerowanymi mapami (`gradcam/DISCLAIMER.txt`); pełna lista ograniczeń: [docs/explainability.md](../explainability.md).

```python
GRADCAM_DISCLAIMER = (
    "Grad-CAM highlights regions associated with the model output. "
    "It is not a biological explanation and must not be used as a diagnosis."
)
```

**Częsty błąd początkującego**: używanie Grad-CAM jako *zamiennika* analizy błędów (punkt 50) — "spojrzałem na mapę ciepła, wygląda OK, więc model jest dobry". To nieweryfikowalne bez maski referencyjnej (ground truth) i nie zastępuje policzenia rzeczywistych metryk na zbiorze testowym.

**Pytanie rekrutacyjne**: W tym repozytorium nie istnieje żadna maska referencyjna (ground-truth) regionu nowotworowego do porównania z mapą Grad-CAM. Co to oznacza dla możliwości *zweryfikowania*, czy mapa jest "biologicznie słuszna"?

---

## 55. Dane syntetyczne vs rzeczywiste

Dane syntetyczne to w pełni wygenerowane (nie pochodzące z rzeczywistych obrazów) dane, używane tu wyłącznie do szybkiego prototypowania, testów jednostkowych i CI — nigdy do wnioskowania o realnej wydajności diagnostycznej. Wyraźnie różne pod każdym względem (wizualnie, statystycznie) od prawdziwej tkanki.

**Gdzie w repo**: `medrisk_ml/data/synthetic.py::SyntheticHistopathologyDataset` — "negative" to rozmyty szum, "positive" to ten sam szum plus jaśniejsza, ustrukturyzowana plama blisko centrum. `medrisk_ml/constants.py::SYNTHETIC_DATA_WARNING` jest wypisywane przez CLI przy każdym użyciu tych danych.

```python
SYNTHETIC_DATA_WARNING = "SYNTHETIC DATA - NOT MEDICAL PERFORMANCE"
```

**Częsty błąd początkującego**: cytowanie metryk z eksperymentu na danych syntetycznych (np. "model osiągnął ROC-AUC 0.95!") bez kontekstu, że to zadanie jest celowo trywialne (centralna jasna plama na szumie) i nie mówi nic o realnej diagnostyce. Stąd manifest modelu wymusza `synthetic_only=True` → `eligible_for_demo=False` (patrz punkt 57).

**Pytanie rekrutacyjne**: Czemu generator danych syntetycznych używa `np.random.default_rng([seed, split_offset, index])` per próbka, zamiast jednego generatora iterowanego sekwencyjnie przez cały dataset?

---

## 56. Bias datasetu (na przykładzie PCam)

Bias datasetu to systematyczne ograniczenie w tym, *jakie* dane zostały zebrane i jak zostały oznaczone — wpływa na to, do czego model faktycznie się generalizuje, niezależnie od tego, jak dobre metryki uzyska na tym samym zbiorze.

**Gdzie w repo**: pełna karta w [docs/dataset-card-pcam.md](../dataset-card-pcam.md); kluczowe ograniczenia PCam: (1) etykieta zależy tylko od **centralnych 32×32 px** łatki, nie od całej łatki; (2) wszystkie dane pochodzą z jednego źródła (Camelyon16, dwa skanery); (3) ewaluacja jest na poziomie łatki, nie pacjenta/preparatu — wiele łatek z tego samego preparatu są ze sobą korelowane, nie niezależne.

```python
# medrisk_ml/data/download.py — nawet samo pobranie nie dzieje się "domyślnie"
ESTIMATED_PCAM_SIZE_GB = 7.0
```

**Częsty błąd początkującego**: interpretowanie wysokiej dokładności na teście PCam jako dowodu, że model "umie wykrywać nowotwór" w sensie ogólnym. Model umie wykrywać dokładnie to, czego nauczył się z tej jednej, konkretnej definicji etykiety i tego jednego źródła danych — nic więcej nie jest zmierzone.

**Pytanie rekrutacyjne**: Łatka ma rozległą tkankę nowotworową na obrzeżach, ale nie w centralnym kwadracie 32×32 px. Jaką etykietę przypisuje jej PCam, i czy to jest "błąd" w etykietowaniu, czy świadoma definicja zadania?

---

## 57. Model registry i experiment tracking

Experiment tracking zapisuje *każdą* próbę treningową (udaną czy nie) w jednym, przeszukiwalnym miejscu — co było trenowane, z jaką konfiguracją, z jakim wynikiem. Model registry to coś innego: świadomy, ręczny krok "to konkretne, wytrenowane i wyewaluowane archiwum zasługuje na bycie nazwanym i zarejestrowanym modelem".

**Gdzie w repo**: `medrisk_ml/registry/registry.py::ExperimentRegistry` (append-only JSONL, `artifacts/registry/experiments.jsonl`) i `ModelRegistry` (katalogi walidowane przy rejestracji) — bez płatnych narzędzi typu MLflow/W&B, celowo proste: plik, który można `grep`ować, i drzewo katalogów, które można `ls`ować.

```python
if manifest.synthetic_only and manifest.eligible_for_demo:
    raise ModelRegistrationError("A synthetic_only model cannot be eligible_for_demo")
```

**Częsty błąd początkującego**: traktowanie "zapisanego checkpointu" jako równoważnego "zarejestrowanemu modelowi". Rejestracja wymaga *uprzedniej* ewaluacji (`metrics.json` musi istnieć) i jawnie oznacza model syntetyczny jako nieadekwatny do demo — to dwa różne poziomy "gotowości", rozdzielone specjalnie, by nie zlały się w jeden przypadkowo.

**Pytanie rekrutacyjne**: Czemu `ExperimentRegistry.append` rzuca błąd dla zduplikowanego `experiment_id`, podczas gdy `_new_experiment_id` (w `cli.py`) generuje ID zawierające znacznik czasu *i* losowy sufiks — czy kolizja w ogóle powinna być praktycznie możliwa?

---

## 58. Model bundle (przenośny pakiet modelu)

Model bundle to samodzielny, przenośny katalog ze wszystkim potrzebnym do inferencji — wagami, metadanymi preprocessingu, progiem, kalibracją, kartą modelu, sumami kontrolnymi — ale **bez** żadnego kodu treningowego. Zaprojektowany tak, by Faza 3 mogła go wczytać bez zależności od czegokolwiek specyficznego dla Fazy 2 (klas datasetów, pętli treningowej, CLI).

**Gdzie w repo**: `medrisk_ml/registry/bundle.py::build_bundle` — kończy się **zawsze** samo-weryfikacją obejmującą inferencję na losowym tensorze o zadeklarowanym kształcie wejścia; model, który nie umie wyprodukować wyjścia, to błąd wykryty *natychmiast*, nie odkryty później w Fazie 3.

```python
BUNDLE_FILES = (
    "model_state.pt", "manifest.json", "preprocessing.json",
    "threshold.json", "calibration.json", "model_card.md",
)
```

**Częsty błąd początkującego**: traktowanie checkpointu treningowego (punkt 37) i bundla jako tego samego artefaktu. Checkpoint zawiera też stan optimizera/schedulera (do wznowienia treningu) — bundle jest *czystszy* i mniejszy, zawiera tylko to, czego potrzebuje sama inferencja.

**Pytanie rekrutacyjne**: Co konkretnie sprawdza `verify_bundle` poza samym istnieniem plików — i czemu zwraca `BundleVerificationResult(valid=False, errors=[...])` zamiast rzucać wyjątek?

---

## 59. Model card (karta modelu)

Karta modelu to ustandaryzowany dokument opisujący model: do czego służy (i do czego nie), na jakich danych był trenowany/testowany, jakie ma wyniki i jakie ograniczenia — odpowiedzialna praktyka udostępniania modeli ML, niezależnie od tego, czy model jest "produkcyjny" czy eksperymentalny.

**Gdzie w repo**: krótka wersja generowana automatycznie do każdego bundla (`medrisk_ml/cli.py::_render_model_card`); pełny, wypełniany ręcznie szablon: [docs/model-card-template.md](../model-card-template.md).

```python
lines = [
    f"# Model card: {manifest.model_name} v{manifest.model_version}",
    ...
    "See docs/model-card-template.md for the full template this summarizes.",
    "",
    MEDICAL_DISCLAIMER,
]
```

**Częsty błąd początkującego**: zadowalanie się automatycznie wygenerowaną kartą jako kompletną dokumentacją. Automatyczna wersja podsumowuje tylko liczby z manifestu — sekcje narracyjne (intended use, known limitations, ethical considerations) wymagają świadomego, ręcznego wypełnienia przez osobę, która rozumie kontekst tego konkretnego modelu.

**Pytanie rekrutacyjne**: Dlaczego automatycznie generowana karta modelu zawsze zawiera pełny disclaimer medyczny, niezależnie od tego, czy model jest oznaczony jako `synthetic_only`?

---

## 60. Smoke test pipeline'u ML

"Smoke test" (test dymny) to szybki, end-to-end test sprawdzający, że cały pipeline *w ogóle działa* (dane → model → trening → checkpoint → ewaluacja → kalibracja → Grad-CAM → bundle), bez ambicji wytrenowania użytecznego modelu — nazwa pochodzi z elektroniki: "włącz urządzenie, sprawdź, czy nie zaczyna dymić."

**Gdzie w repo**: `configs/ml/smoke.yaml` (mały syntetyczny dataset, 2 epoki, batch 16 — całość w sekundach na CPU) i `tests/ml/test_smoke_training.py::test_full_synthetic_smoke_pipeline`, uruchamiany w CI przy każdej zmianie.

```python
# tests/ml/test_smoke_training.py
roc_auc = evaluation_result.test_metrics["roc_auc"]
assert roc_auc is not None and roc_auc >= 0.6  # type: ignore[operator]
```

**Częsty błąd początkującego**: traktowanie przejścia smoke testu jako dowodu, że model "działa dobrze". Smoke test sprawdza tylko, że *infrastruktura* (kod, nie jakość modelu) nie jest zepsuta — próg `roc_auc >= 0.6` na trywialnym syntetycznym zadaniu to sanity check ("uczy się czegokolwiek nielosowego"), nie cel wydajnościowy.

**Pytanie rekrutacyjne**: Czemu próg w smoke teście to `0.6`, a nie np. `0.95` — co by się stało, gdyby próg był ustawiony zbyt wysoko dla tak małego, szybkiego eksperymentu?

---

## Pytania kontrolne

1. Czemu model w tym projekcie zwraca logity `(batch, 1)`, a nie prawdopodobieństwa `(batch,)` — i gdzie dokładnie w kodzie następuje jedyne "ściśnięcie" wymiaru?
2. Co dokładnie różni dane treningowe, walidacyjne i testowe pod względem tego, *do czego wolno* je użyć w tym pipeline?
3. Dlaczego `select_threshold` rzuca `SplitLeakageError`, gdy `split_name="test"`, a nie po prostu komentarz ostrzegawczy w docstringu?
4. Jak `np.random.default_rng([seed, split_offset, index])` w danych syntetycznych różni się od użycia wbudowanego `hash()` Pythona, i czemu to drugie byłoby błędem?
5. Co się stanie, jeśli ustawisz `runtime.deterministic: true` i `runtime.benchmark: true` jednocześnie w configu?
6. Czemu `baseline_cnn` nie może mieć `model.pretrained: true` w configu — co to oznaczałoby w praktyce, gdyby było dozwolone?
7. Jaka jest różnica między zamrożeniem warstwy (`requires_grad=False`) a nieprzekazaniem jej do optimizera?
8. Dlaczego ResNet18 (Stage A) i fine-tuning (Stage B) to dwa odrębne, ręcznie wywoływane kroki, a nie jedna automatyczna sekwencja?
9. Co dokładnie zawiera plik checkpointu poza wagami modelu, i czemu te dodatkowe pola są tam zapisane?
10. Czym różni się `best.pt` od `last.pt`, i które z nich wczytuje `evaluate`/`explain`/`register`?
11. Dlaczego `compute_binary_metrics` zwraca `float("nan")` dla `roc_auc`, gdy w danych jest tylko jedna klasa, zamiast np. `0.0`?
12. Co dokładnie sprawdza, i czego NIE sprawdza, próg wybrany strategią `youden_j` w porównaniu do `max_f1`?
13. Czemu kalibracja (temperature scaling) nigdy nie zmienia ROC-AUC ani PR-AUC modelu?
14. Co mówi bootstrapowy przedział ufności o niepewności modelu, a czego o tej niepewności *nie* mówi?
15. Jakie konkretnie kategorie próbek wybiera `cmd_explain` do wygenerowania map Grad-CAM, jeśli dostępne są wyniki z `evaluate`?
16. Dlaczego Grad-CAM dla modelu binarnego nie potrzebuje wybierać "klasy", dla której liczy mapę?
17. Co dokładnie robi `ActivationsAndGradients.release()`, i co by się stało, gdyby nigdy nie było wywołane przy wielokrotnym użyciu `GradCAM` w pętli?
18. Czym różni się analiza błędów (`error_analysis.py`) od samego Grad-CAM jako narzędzia do zrozumienia, gdzie model się myli?
19. Dlaczego `ModelRegistry.register` odmawia zarejestrowania modelu, dla którego `synthetic_only=True` i `eligible_for_demo=True` jednocześnie?
20. Co dokładnie sprawdza `verify_bundle` poza zgodnością sum kontrolnych plików?
21. Jaka jest różnica między eksperymentem w `ExperimentRegistry` a modelem w `ModelRegistry` — czy każdy eksperyment staje się modelem?
22. Dlaczego pobranie prawdziwego PCam wymaga *dwóch* niezależnych warunków (flagi CLI i zmiennej środowiskowej), a nie jednego?
23. Co oznacza etykieta "positive" w PCam dokładnie — cała łatka zawiera tkankę nowotworową, czy tylko jej centralny fragment?
24. Czemu ewaluacja na poziomie pojedynczej łatki nie mówi nic bezpośrednio o wydajności na poziomie pacjenta/preparatu?
25. Co dokładnie różni augmentację danych stosowaną w treningu od transformacji stosowanej w ewaluacji/inferencji?
26. Dlaczego normalizacja dla `resnet18` używa stałych statystyk ImageNet, a dla `baseline_cnn` — statystyk liczonych z własnego zbioru treningowego?
27. Co się stanie, jeśli `--set` override w CLI odwołuje się do nieistniejącego pola konfiguracji (np. `training.nonexistent_field=1`)?
28. Dlaczego `pyproject.toml` ma `filterwarnings = ["error"]` dla pytest, i jak to wpłynęło na sposób, w jaki napisane są niektóre obliczenia w `medrisk_ml/evaluation/`?
29. Co dokładnie odróżnia "smoke test" od pełnowartościowego eksperymentu na rzeczywistych danych — co smoke test *udowadnia*, a czego nie udowadnia?
30. Dlaczego żaden plik w `medrisk_ml/` nie importuje niczego z `app/`, i odwrotnie?

## Zadania do samodzielnego wykonania

Każde z poniższych zadań można wykonać w pełni na danych syntetycznych, bez pobierania prawdziwego PCam i bez psowania istniejącej funkcjonalności — przed wysłaniem zmian uruchom `python scripts/check.py`.

1. **Dodaj nową metrykę.** Dodaj do `compute_binary_metrics` współczynnik Matthewsa (Matthews Correlation Coefficient, MCC) — zaimplementuj formułę z confusion matrix, obsłuż przypadek niezdefiniowany (mianownik = 0) zgodnie z istniejącą polityką `nan`, i dodaj test w `tests/ml/test_metrics.py`.
2. **Dodaj nową strategię wyboru progu.** Zaimplementuj strategię `min_cost` w `select_threshold`, przyjmującą koszty FP i FN jako parametry, minimalizującą `cost = fp_cost * FP + fn_cost * FN`. Napisz test porównujący ją z `youden_j` na tym samym, w pełni rozdzielnym zbiorze z `test_thresholding.py`.
3. **Napisz test brzegowego przypadku.** Sprawdź, co dzieje się w `compute_binary_metrics`, gdy *wszystkie* próbki mają tę samą etykietę (same negatywne) — zweryfikuj, które metryki są `nan`, a które są dobrze zdefiniowane, i dodaj asercje dla obu grup.
4. **Eksperyment z hiperparametrami.** Uruchom `train` na `configs/ml/smoke.yaml` trzy razy z różnym `--set training.learning_rate=...` (np. `0.1`, `0.001`, `0.00001`), porównaj `training_history.csv` z każdego przebiegu i napisz krótką notatkę (w komentarzu lub osobnym pliku w `artifacts/`), który learning rate "rozjeżdża" trening, a który jest zbyt wolny.
5. **Sprawdź reprodukowalność empirycznie.** Uruchom dokładnie ten sam `train` na `configs/ml/smoke.yaml` dwa razy pod rząd (ten sam seed, `runtime.deterministic: true`). Porównaj `training_history.json` z obu przebiegów — czy liczby są identyczne? Zapisz, co dokładnie sprawdziłeś i jaki był wynik.
6. **Dodaj nową kategorię błędów.** Rozszerz `error_analysis.py` o nową funkcję, np. `most_improved_by_calibration` — próbki, dla których kalibracja zmieniła decyzję (próg ten sam, ale `calibrated_probability` i `uncalibrated_probability` są po różnych stronach progu). Podłącz wynik do `write_error_analysis`.
7. **Zdekoduj i opisz checkpoint.** Wczytaj checkpoint z dowolnego przebiegu smoke (`load_checkpoint`) w osobnym skrypcie/REPL i wypisz wszystkie pola poza `model_state_dict`. Wyjaśnij (w komentarzu), do czego każde z nich służyłoby, gdyby trzeba było wznowić trening od tego punktu.
8. **Wygeneruj i opisz Grad-CAM na własnych przykładach.** Uruchom `explain` na wyniku smoke-eksperymentu, obejrzyj wygenerowane mapy. Dla jednego "true positive" i jednego "false positive" opisz (krótko, słowami), co widzisz na mapie — i osobnym zdaniem wyraźnie zaznacz, że to nie jest interpretacja medyczna (patrz disclaimer w punkcie 51/54).
9. **Dodaj pole do `ModelManifest` i zaktualizuj walidację.** Dodaj opcjonalne pole `notes: str | None` do `ModelManifest`, zaktualizuj `_make_manifest` w `tests/ml/test_registry.py`, i upewnij się, że `mypy`/`ruff`/`pytest` przechodzą bez zmiany zachowania istniejących testów.
10. **Napisz test na uszkodzony bundle.** Dodaj do `tests/ml/test_registry.py` test, który psuje `model_state.pt` (np. obcina plik o kilka bajtów) i sprawdza, że `verify_bundle` zwraca `valid=False` z sensownym błędem w `errors`, a nie rzuca nieobsłużony wyjątek.
11. **Zaimplementuj prostą `review_policy`.** Manifest ma pole `review_policy: dict | None`, ale nic go jeszcze nie odczytuje. Napisz funkcję `should_route_to_human_review(probability, threshold, review_policy)`, która (np. dla `review_policy={"band": 0.1}`) zwraca `True`, gdy predykcja jest w paśmie niepewności wokół progu — wraz z testami.
12. **Porównaj `baseline_cnn` i `resnet18` na danych syntetycznych.** Uruchom `train` + `evaluate` dla obu architektur na tym samym, syntetycznym configu (skopiuj `smoke.yaml`, zmień tylko `model.architecture` i odpowiednie pola). Porównaj `metrics.json` z obu przebiegów i zapisz wniosek — pamiętając, że to porównanie mówi tylko o trywialnym zadaniu syntetycznym, nie o realnej wydajności diagnostycznej.

