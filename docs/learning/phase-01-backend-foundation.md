# Faza 1: Fundament backendu — przewodnik edukacyjny

Ten dokument jest napisany dla osoby, która zna podstawy Pythona, ale dopiero zaczyna pracę z FastAPI, bazami danych i testowaniem backendu. Każda sekcja: proste wyjaśnienie → gdzie to jest w tym repozytorium → krótki przykład kodu → częsty błąd początkujących → pytanie w stylu rekrutacyjnym.

---

## 1. Czym jest backend

Backend to część aplikacji, która działa po stronie serwera: przyjmuje żądania (requesty), wykonuje logikę biznesową, rozmawia z bazą danych i zwraca odpowiedź. Użytkownik nigdy nie widzi kodu backendu — widzi tylko efekty jego działania (np. dane w aplikacji mobilnej).

**Gdzie w repo**: cały katalog `app/` to backend — nie ma tu żadnego HTML/JS/UI.

```python
# app/main.py — to jest "wejście" do backendu
app = create_app()
```

**Częsty błąd początkującego**: mylenie backendu z "serwerem" w sensie fizycznym. Backend to *kod*, który może działać na laptopie, w kontenerze Docker albo na serwerze w chmurze — to nie miejsce, to rola.

**Pytanie rekrutacyjne**: Czym różni się backend od frontendu i jakie dane powinny być walidowane na backendzie, nawet jeśli frontend już je waliduje?

---

## 2. Czym jest REST API

REST API to sposób komunikacji między klientem a serwerem przez HTTP, gdzie każdy "zasób" (np. użytkownik, predykcja) ma swój adres URL, a operacje na nim wyrażamy metodami HTTP (`GET` = odczyt, `POST` = stworzenie, itd.).

**Gdzie w repo**: `GET /api/v1/users/me`, `POST /api/v1/auth/register` — adres + metoda = jedna konkretna operacja.

```python
@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(current_user)
```

**Częsty błąd początkującego**: używanie `GET` do operacji, które zmieniają dane (np. `GET /delete-user`). `GET` powinien być "bezpieczny" — nigdy nie zmieniać stanu serwera.

**Pytanie rekrutacyjne**: Dlaczego logowanie w tym projekcie jest `POST`, a nie `GET`, mimo że dane logowania moglibyśmy teoretycznie wysłać w URL?

---

## 3. Request i response

Request to żądanie wysłane przez klienta (metoda, URL, nagłówki, ewentualnie body). Response to odpowiedź serwera (status code, nagłówki, body). FastAPI automatycznie zamienia oba na/z obiektów Pythona.

**Gdzie w repo**: `app/middleware/request_id.py` operuje bezpośrednio na surowym requeście/response na poziomie ASGI.

```python
async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "http":
        await self.app(scope, receive, send)
        return
```

**Częsty błąd początkującego**: zakładanie, że request "czeka" na jedną odpowiedź — w rzeczywistości to wymiana wiadomości ASGI (`http.request`, `http.response.start`, `http.response.body`), co widać właśnie w middleware.

**Pytanie rekrutacyjne**: Co dokładnie znajduje się w nagłówkach żądania HTTP wysyłanego do `/api/v1/users/me`, żeby serwer wiedział, kto pyta?

---

## 4. Endpoint

Endpoint to konkretna funkcja obsługująca konkretną kombinację metody HTTP i ścieżki URL.

**Gdzie w repo**: `app/api/v1/endpoints/predictions.py` — każda funkcja ozdobiona `@router.post(...)` lub `@router.get(...)` to jeden endpoint.

```python
@router.get("/history", response_model=Page[PredictionRead])
async def get_history(
    current_user: CurrentUserDep,
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[PredictionRead]:
    ...
```

**Częsty błąd początkującego**: wpisywanie całej logiki biznesowej (zapytania SQL, reguły) prosto w funkcję endpointu. W tym projekcie endpoint tylko *woła* warstwę `services` — sam nie wie, jak coś jest zaimplementowane.

**Pytanie rekrutacyjne**: Co powinien zrobić endpoint, jeśli warstwa serwisowa zgłosi wyjątek domenowy (np. `ConflictError`), a co — gdy zgłosi coś nieoczekiwanego?

---

## 5. Router

Router grupuje powiązane endpointy i pozwala montować je pod wspólnym prefiksem URL.

**Gdzie w repo**: `app/api/v1/router.py` zbiera routery `auth`, `users`, `predictions`; `app/api/router.py` montuje całość pod `/api/v1`, a `health` osobno, bez prefiksu.

```python
api_v1_router = APIRouter()
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(users.router, prefix="/users", tags=["users"])
```

**Częsty błąd początkującego**: definiowanie wszystkich endpointów w jednym wielkim pliku `main.py`. Routery istnieją właśnie, żeby tego uniknąć — każdy obszar (auth, users, predictions) ma własny plik.

**Pytanie rekrutacyjne**: Dlaczego endpointy `/health/live` i `/health/ready` NIE są zamontowane pod `/api/v1`, w odróżnieniu od `/api/v1/auth/login`?

---

## 6. Dependency injection w FastAPI

Dependency injection (wstrzykiwanie zależności) to mechanizm, w którym FastAPI samo dostarcza funkcji-endpointowi to, czego potrzebuje (np. sesję bazy danych, zalogowanego użytkownika) — endpoint nie tworzy tych obiektów sam.

**Gdzie w repo**: `app/api/dependencies.py`.

```python
SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
```

Dzięki temu endpoint po prostu deklaruje `session: DbSessionDep` w sygnaturze, a FastAPI samo wywołuje `get_db_session()` i przekazuje wynik.

**Częsty błąd początkującego**: tworzenie sesji bazy danych "ręcznie" wewnątrz funkcji endpointu (`session = AsyncSessionLocal()`) — wtedy nikt nie gwarantuje, że sesja zostanie poprawnie zamknięta przy błędzie.

**Pytanie rekrutacyjne**: Co się stanie, jeśli dwa równoległe requesty użyją tej samej zależności `get_db_session` — dostaną tę samą sesję, czy dwie różne?

---

## 7. Pydantic schema

Schema (schemat) Pydantic to klasa opisująca *kształt* danych wejściowych/wyjściowych API: jakie pola, jakie typy, jakie reguły walidacji.

**Gdzie w repo**: `app/schemas/auth.py`.

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
```

Jeśli klient wyśle hasło krótsze niż 12 znaków, FastAPI samo odrzuci żądanie z kodem `422` — endpoint nigdy nie zobaczy nieprawidłowych danych.

**Częsty błąd początkującego**: używanie modelu bazy danych (ORM) jako bezpośredniej odpowiedzi API. Wtedy łatwo przypadkowo zwrócić pole, które nigdy nie powinno wyjść z serwera (np. `hashed_password`).

**Pytanie rekrutacyjne**: Czym różni się walidacja danych wejściowych (np. `RegisterRequest`) od serializacji danych wyjściowych (np. `UserRead`) i czemu to dwa różne schematy, a nie jeden?

---

## 8. Model ORM

Model ORM (Object-Relational Mapping) to klasa Pythona reprezentująca tabelę w bazie danych — jej atrybuty to kolumny, a instancja klasy to jeden wiersz.

**Gdzie w repo**: `app/models/user.py`.

```python
class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
```

**Częsty błąd początkującego**: traktowanie modelu ORM jako "tego samego" co schema Pydantic. To dwa różne światy — patrz punkt 9.

**Pytanie rekrutacyjne**: Jeśli dodasz nowe pole do modelu `User`, czy ono automatycznie pojawi się w bazie danych? (Odpowiedź: nie — patrz punkt 19, Alembic.)

---

## 9. Różnica między schematem Pydantic a modelem SQLAlchemy

Model SQLAlchemy opisuje **jak dane są przechowywane** w bazie. Schema Pydantic opisuje **jak dane wchodzą i wychodzą** przez API. To są niezależne warstwy — celowo.

**Gdzie w repo**: `app/models/user.py` (ORM) vs. `app/schemas/user.py` (Pydantic) — `UserRead` ma podzbiór pól `User` i nigdy `hashed_password`.

```python
# Model (baza danych) ma hashed_password.
# Schema (API) - nie ma go wcale:
class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str
```

**Częsty błąd początkującego**: zwracanie modelu ORM prosto z endpointu (`return user`) bez przejścia przez schemat — w FastAPI to czasem "działa" przypadkiem, ale nie kontrolujesz, co naprawdę trafia do klienta.

**Pytanie rekrutacyjne**: Dlaczego `UserRead` ma `model_config = ConfigDict(from_attributes=True)` — co by się stało bez tego?

---

## 10. Tabela i rekord

Tabela to zbiór wierszy o tej samej strukturze (kolumnach). Rekord (wiersz) to jeden konkretny zestaw wartości w tej tabeli — np. jeden użytkownik.

**Gdzie w repo**: tabela `users` (zdefiniowana w migracji `alembic/versions/..._create_initial_schema.py`), rekord — jeden konkretny wiersz, np. zwrócony przez `user_repo.get_by_email(...)`.

```python
async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
```

**Częsty błąd początkującego**: mylenie "tabeli" (struktury) z "modelem" (klasą Pythona) — model *opisuje* tabelę, ale nie jest nią.

**Pytanie rekrutacyjne**: Co zwróci `get_by_email`, jeśli w tabeli nie ma żadnego rekordu z danym adresem e-mail?

---

## 11. Primary key

Primary key (klucz główny) to kolumna (lub zestaw kolumn) jednoznacznie identyfikująca każdy wiersz w tabeli. W tym projekcie to zawsze UUID generowany po stronie Pythona.

**Gdzie w repo**: `app/models/mixins.py`.

```python
class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

**Częsty błąd początkującego**: używanie autoincrementowanego `int` jako klucza głównego w publicznym API — kolejne ID (1, 2, 3...) ujawniają, ile rekordów istnieje, i są łatwe do odgadnięcia/przeskanowania. UUID tego nie robi.

**Pytanie rekrutacyjne**: Czy dwa różne wiersze mogą mieć ten sam `id`? Co gwarantuje, że nie?

---

## 12. Foreign key

Foreign key (klucz zewnętrzny) to kolumna, która wskazuje na primary key w *innej* tabeli — tak wyrażamy relacje (np. "ta predykcja należy do tego użytkownika").

**Gdzie w repo**: `app/models/prediction.py`.

```python
user_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
)
```

`ondelete="CASCADE"` oznacza: jeśli usuniesz użytkownika, baza danych automatycznie usunie też wszystkie jego predykcje i sesje odświeżania tokenu.

**Częsty błąd początkującego**: zapominanie o indeksie na kolumnie klucza zewnętrznego — bez niego zapytania typu "wszystkie predykcje tego użytkownika" muszą przeskanować całą tabelę.

**Pytanie rekrutacyjne**: Co się stanie, jeśli spróbujesz wstawić predykcję z `user_id`, które nie istnieje w tabeli `users`?

---

## 13. Indeks

Indeks to dodatkowa struktura danych, którą baza danych utrzymuje, żeby szybko wyszukiwać wiersze po danej kolumnie — kosztem odrobiny miejsca i wolniejszych zapisów.

**Gdzie w repo**: `app/models/prediction.py` ma indeks złożony specjalnie pod zapytanie "historia użytkownika, od najnowszych".

```python
__table_args__ = (Index("ix_predictions_user_id_created_at", "user_id", "created_at"),)
```

**Częsty błąd początkującego**: dodawanie indeksu na każdej kolumnie "na wszelki wypadek". Indeksy nie są darmowe — każdy `INSERT`/`UPDATE` musi je zaktualizować.

**Pytanie rekrutacyjne**: Dlaczego indeks na `(user_id, created_at)` pomaga zapytaniu `WHERE user_id = ... ORDER BY created_at DESC`, a osobne indeksy na `user_id` i na `created_at` pomogłyby mniej?

---

## 14. Transakcja

Transakcja to grupa operacji na bazie danych, które wykonują się **wszystkie albo żadna** — gwarancja atomowości.

**Gdzie w repo**: rotacja refresh tokenu (`app/services/auth.py:rotate_refresh_token`) unieważnia stary token i tworzy nowy — to musi się zdarzyć razem, inaczej użytkownik mógłby zostać bez działającego tokenu.

```python
await refresh_token_repo.revoke(session, stored_session, replaced_by_jti=new_refresh.jti)
await refresh_token_repo.create(session, ...)
await session.commit()  # dopiero teraz obie zmiany są trwałe
```

**Częsty błąd początkującego**: wywoływanie `commit()` po każdej pojedynczej operacji w wielu miejscach — wtedy nie ma gwarancji, że "wszystko albo nic" naprawdę zadziała, jeśli druga operacja zawiedzie.

**Pytanie rekrutacyjne**: Co by się stało, gdyby `commit()` był wywołany od razu po `revoke(...)`, a `create(...)` rzuciło wyjątek?

---

## 15. Commit

`commit()` trwale zapisuje wszystkie zmiany zrobione w ramach bieżącej transakcji.

**Gdzie w repo**: warstwa `services` jest jedynym miejscem, które wywołuje `session.commit()` w tym projekcie — to świadoma decyzja architektoniczna (patrz `docs/architecture.md`, sekcja "granica transakcji").

```python
async def register_user(session: AsyncSession, *, email: str, password: str, full_name: str) -> User:
    ...
    user = await user_repo.create(session, email=normalized_email, ...)
    await session.commit()
    return user
```

**Częsty błąd początkującego**: wywoływanie `commit()` w warstwie repozytorium. Wtedy repozytorium decyduje "za" serwis, kiedy dane stają się trwałe — utrudnia to łączenie kilku operacji w jedną transakcję.

**Pytanie rekrutacyjne**: Czy `user_repo.create(...)` w tym projekcie wywołuje `commit()`? Sprawdź `app/repositories/user.py`.

---

## 16. Rollback

`rollback()` wycofuje wszystkie niezatwierdzone zmiany w bieżącej transakcji — tak jakby się nigdy nie wydarzyły.

**Gdzie w repo**: `app/db/session.py:get_db_session` — jeśli podczas requestu wystąpi wyjątek, sesja wykonuje rollback *przed* zamknięciem.

```python
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Częsty błąd początkującego**: zakładanie, że samo zamknięcie sesji (`close()`) "anuluje" niezatwierdzone zmiany. Zachowanie przy zamknięciu bez wcześniejszego rollbacku zależy od sterownika i nie jest czymś, na czym warto polegać — rollback trzeba wykonać explicite.

**Pytanie rekrutacyjne**: Jeśli endpoint zwróci błąd walidacji (422) *przed* dotknięciem bazy danych, czy w ogóle dojdzie do rollbacku?

---

## 17. AsyncSession

`AsyncSession` to obiekt SQLAlchemy reprezentujący "rozmowę" z bazą danych — zapytania, dodawanie obiektów, commit/rollback — w wersji asynchronicznej (`await`).

**Gdzie w repo**: `app/db/session.py`.

```python
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
```

`AsyncSessionLocal` to "fabryka" sesji — każde jej wywołanie tworzy nową, niezależną sesję.

**Częsty błąd początkującego**: tworzenie jednej sesji przy starcie aplikacji i używanie jej do obsługi wszystkich requestów. To prowadzi do punktu 18.

**Pytanie rekrutacyjne**: Czym różni się `Engine` od `Session` w SQLAlchemy — dlaczego jeden jest globalny, a drugi tworzony na nowo dla każdego requestu?

---

## 18. Dlaczego sesji nie współdzielimy między równoległymi requestami

`AsyncSession` nie jest bezpieczna do współdzielenia między współbieżnymi zadaniami (np. dwoma requestami obsługiwanymi "w tym samym czasie" przez event loop). Ma swój wewnętrzny stan (otwartą transakcję, śledzone obiekty) — dwa requesty używające tej samej sesji mogłyby zobaczyć cudze niezatwierdzone zmiany albo wywołać `commit()`/`rollback()` w złym momencie dla drugiego żądania.

**Gdzie w repo**: właśnie dlatego `get_db_session` (punkt 6) tworzy nową sesję *za każdym razem*, gdy FastAPI go wywołuje — czyli raz na request.

**Częsty błąd początkującego**: zdefiniowanie `session = AsyncSessionLocal()` jako zmiennej globalnej "żeby było szybciej" — to optymalizacja, która łamie poprawność programu.

**Pytanie rekrutacyjne**: Dwóch użytkowników loguje się w tym samym momencie. Czy ich requesty mogą bezpiecznie używać tego samego obiektu `Engine`? A tego samego obiektu `AsyncSession`?

---

## 19. Alembic i migracje

Migracja to wersjonowana, odtwarzalna zmiana schematu bazy danych (np. "dodaj tabelę users"). Alembic zarządza historią tych zmian i wie, jaka jest aktualna wersja schematu.

**Gdzie w repo**: `alembic/versions/6936f012d734_create_initial_schema.py` — pierwsza migracja, tworząca wszystkie tabele Fazy 1.

```bash
alembic revision --autogenerate -m "create initial schema"   # wygeneruj
alembic upgrade head                                          # zastosuj
alembic check                                                  # sprawdź, czy modele i baza są zgodne
```

**Częsty błąd początkującego**: ślepe ufanie automatycznie wygenerowanej migracji. W tym projekcie autogenerate *nie* wygenerował poprawnego `downgrade()` dla natywnych enumów PostgreSQL — trzeba było to dopisać ręcznie (patrz `docs/database.md`).

**Pytanie rekrutacyjne**: Dodajesz nowe pole do modelu `User`. Jakie dokładnie polecenia musisz wykonać, żeby ta zmiana trafiła do bazy danych?

---

## 20. JWT

JWT (JSON Web Token) to ciąg znaków zawierający zakodowane (nie zaszyfrowane!) dane (claims) plus podpis kryptograficzny — odbiorca może zweryfikować, że dane nie zostały zmienione i że pochodzą od kogoś, kto znał sekret.

**Gdzie w repo**: `app/core/security.py`.

```python
payload = {"sub": subject, "type": token_type, "iat": ..., "exp": ..., "iss": ..., "aud": ..., "jti": jti}
token = jwt.encode(payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALGORITHM)
```

**Częsty błąd początkującego**: traktowanie JWT jako "bezpiecznego schowka" na dane, bo "są zakodowane". Każdy może zdekodować JWT i odczytać jego zawartość (np. na jwt.io) — JWT gwarantuje integralność, nie tajność.

**Pytanie rekrutacyjne**: Czy ktoś, kto przechwyci poprawny JWT, może odczytać `sub` bez znajomości `JWT_SECRET_KEY`? A czy może go *zmodyfikować* i nadal przejść weryfikację?

---

## 21. Access token

Access token to krótkotrwały JWT (tu: 15 minut), używany do autoryzacji *każdego* żądania do chronionego endpointu. Krótki czas życia ogranicza szkody, jeśli token wycieknie.

**Gdzie w repo**: `app/api/dependencies.py:get_current_user` weryfikuje, że token ma `type == "access"`.

```python
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], ...) -> User:
    return await get_authenticated_user(session, settings, access_token=token)
```

**Częsty błąd początkującego**: ustawianie bardzo długiego czasu życia access tokenu "żeby użytkownik nie musiał się często odświeżać" — to bezpośrednio zwiększa okno ryzyka, jeśli token wycieknie, bo access tokenów (w odróżnieniu od refresh tokenów) nie można tu unieważnić przed wygaśnięciem.

**Pytanie rekrutacyjne**: Dlaczego access token NIE jest zapisywany w bazie danych, a refresh token — jest?

---

## 22. Refresh token

Refresh token to długotrwały JWT (tu: 7 dni), używany *tylko* do uzyskania nowej pary tokenów przez `/auth/refresh`. Jest śledzony w bazie danych, więc można go unieważnić.

**Gdzie w repo**: tabela `refresh_token_sessions` + `app/services/auth.py:rotate_refresh_token`.

```python
if stored_session.revoked_at is not None:
    raise TokenRevokedError("This refresh token has already been used or revoked.")
```

**Częsty błąd początkującego**: pozwolenie na wielokrotne użycie tego samego refresh tokenu. Tutaj każde udane odświeżenie *unieważnia* stary token (rotacja) — ponowne użycie jest traktowane jako podejrzane i odrzucane.

**Pytanie rekrutacyjne**: Użytkownik odświeża token na dwóch urządzeniach niemal jednocześnie, używając tego samego refresh tokenu. Co się stanie z drugim żądaniem?

---

## 23. Hashowanie hasła

Hashowanie to jednostronna funkcja matematyczna: z hasła łatwo obliczyć hash, ale z hasha praktycznie niemożliwe odtworzyć hasło. Do weryfikacji logowania nie trzeba *odszyfrowywać* hasła — trzeba ponownie zahashować podane hasło i porównać hashe.

**Gdzie w repo**: `app/core/security.py`.

```python
def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _password_hasher.verify(plain_password, hashed_password)
```

**Częsty błąd początkującego**: przechowywanie hasła "zaszyfrowanego", licząc na to, że można je później odszyfrować. To dokładnie odwrotność tego, czego chcemy — patrz punkt 24.

**Pytanie rekrutacyjne**: Administrator bazy danych z pełnym dostępem do tabeli `users` — czy może odzyskać hasło użytkownika w postaci czytelnej? Czemu tak/nie?

---

## 24. Dlaczego hashowanie nie jest szyfrowaniem

Szyfrowanie jest **odwracalne** (z odpowiednim kluczem można odzyskać oryginał) — używane, gdy *ktoś* musi później odczytać dane. Hashowanie jest **nieodwracalne z założenia** — używane, gdy nikt, nawet właściciel systemu, nie powinien móc odzyskać oryginału.

**Gdzie w repo**: `hashed_password` w `app/models/user.py` — nazwa pola mówi dokładnie, co tam jest: hash, nie zaszyfrowany tekst.

**Częsty błąd początkującego**: używanie tych dwóch słów wymiennie w rozmowie/dokumentacji. To nie synonimy — mylenie ich w rozmowie technicznej (np. na rozmowie o pracę) jest częstym sygnałem ostrzegawczym dla rekrutera.

**Pytanie rekrutacyjne**: Dlaczego do haseł używamy hashowania, a do np. numeru karty płatniczej w systemie, który musi go później pokazać — szyfrowania?

---

## 25. Argon2

Argon2 to algorytm hashowania haseł, zwycięzca Password Hashing Competition (2015), zaprojektowany tak, by być kosztowny obliczeniowo i pamięciowo — co utrudnia atak brute-force, nawet na specjalizowanym sprzęcie (GPU/ASIC).

**Gdzie w repo**: `app/core/security.py` — wybrany jawnie, a nie przez "domyślną rekomendację" biblioteki, która mogłaby się zmienić.

```python
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

_password_hasher = PasswordHash([Argon2Hasher()])
```

**Częsty błąd początkującego**: używanie szybkich funkcji hashujących ogólnego przeznaczenia (np. MD5, SHA-256 bez "soli" i kosztu) do haseł. Te funkcje są zaprojektowane, by być *szybkie* — co jest dobre dla integralności plików, ale fatalne dla haseł (atakujący może sprawdzić miliardy haseł na sekundę).

**Pytanie rekrutacyjne**: Co different Argon2 od "zwykłego" SHA-256 w kontekście odporności na atak brute-force?

---

## 26. Middleware

Middleware to kod, który "owija" każde żądanie/odpowiedź — wykonuje się zawsze, niezależnie od tego, który endpoint zostanie ostatecznie wywołany.

**Gdzie w repo**: `app/middleware/request_id.py`.

```python
class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ...
        await self.app(scope, receive, send_with_request_id)
```

**Częsty błąd początkującego**: umieszczanie logiki specyficznej dla jednego endpointu w middleware. Middleware powinien robić rzeczy *uniwersalne* (request ID, CORS, zaufane hosty) — logika konkretnego endpointu należy do routera/serwisu.

**Pytanie rekrutacyjne**: W jakiej kolejności w tym projekcie wykonują się middleware: `RequestIdMiddleware`, `TrustedHostMiddleware`, `CORSMiddleware`? Sprawdź `app/main.py` i zastanów się, czy kolejność ma znaczenie.

---

## 27. Request ID

Request ID to unikalny identyfikator przypisany do każdego żądania, pozwalający powiązać logi, błędy i odpowiedź z konkretnym requestem — kluczowe przy debugowaniu produkcyjnym, gdzie requesty się przeplatają.

**Gdzie w repo**: `app/middleware/request_id.py` generuje go (albo przyjmuje od klienta, jeśli wygląda bezpiecznie), a `app/core/logging.py` wstrzykuje go do każdej linii logu.

```python
def _resolve_request_id(headers: Headers) -> str:
    incoming = headers.get(REQUEST_ID_HEADER)
    if incoming and _VALID_REQUEST_ID_RE.match(incoming):
        return incoming
    return uuid.uuid4().hex
```

**Częsty błąd początkującego**: bezgraniczne ufanie nagłówkowi `X-Request-ID` od klienta (np. bez walidacji długości/znaków) — w tym projekcie jest sprawdzany regexem, żeby ktoś nie wstrzyknął tam czegoś złośliwego do logów.

**Pytanie rekrutacyjne**: Klient w ogóle nie wysyła nagłówka `X-Request-ID`. Co się stanie?

---

## 28. Test jednostkowy

Test jednostkowy sprawdza jedną, małą jednostkę kodu (np. jedną funkcję) w izolacji, bez zewnętrznych zależności (bazy danych, sieci).

**Gdzie w repo**: `tests/unit/test_security.py`.

```python
def test_verify_password_fails_for_incorrect_password() -> None:
    hashed = hash_password("a-very-secret-password")
    assert verify_password("wrong-password", hashed) is False
```

**Częsty błąd początkującego**: nazywanie "testem jednostkowym" testu, który faktycznie łączy się z bazą danych albo robi żądanie HTTP — to już test integracyjny (punkt 29), nawet jeśli sprawdza tylko jedną funkcję.

**Pytanie rekrutacyjne**: Dlaczego testy w `tests/unit/` w tym projekcie nigdy nie importują niczego z `app/db/` ani `app/repositories/`?

---

## 29. Test integracyjny

Test integracyjny sprawdza, jak współpracują ze sobą realne komponenty — tu: prawdziwa baza danych PostgreSQL i prawdziwa aplikacja FastAPI (wywoływana przez HTTP, ale bez prawdziwego gniazda sieciowego — przez `ASGITransport`).

**Gdzie w repo**: `tests/integration/test_auth.py`.

```python
async def test_login_with_valid_credentials_returns_token_pair(
    client: AsyncClient, registered_user: RegisteredUser
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": registered_user.email, "password": registered_user.password},
    )
    assert response.status_code == 200
```

**Częsty błąd początkującego**: zastępowanie prawdziwej bazy danych w testach integracyjnych przez SQLite albo mocki "dla wygody". Ten projekt świadomie tego unika (patrz `docs/decisions/ADR-001-backend-architecture.md`) — testy integracyjne mają sens tylko, jeśli testują to, co naprawdę działa na produkcji.

**Pytanie rekrutacyjne**: Skąd `tests/integration/conftest.py` wie, że ma użyć bazy `medrisk_test`, a nie `medrisk`?

---

## 30. Docker

Docker pakuje aplikację razem z jej środowiskiem (interpreter Pythona, biblioteki systemowe) w jeden, przenośny obraz (image), który działa identycznie na każdej maszynie.

**Gdzie w repo**: `Dockerfile`.

```dockerfile
FROM python:3.12-slim
...
RUN groupadd --system medrisk && useradd --system --gid medrisk --create-home medrisk \
    && chown -R medrisk:medrisk /app
USER medrisk
```

**Częsty błąd początkującego**: budowanie i uruchamianie kontenera jako `root`. Jeśli ktoś znajdzie sposób, by "wyjść" z kontenera, lepiej żeby miał uprawnienia zwykłego użytkownika, nie administratora.

**Pytanie rekrutacyjne**: Dlaczego `Dockerfile` najpierw kopiuje `requirements.txt` i instaluje zależności, a *potem* kopiuje kod aplikacji — a nie odwrotnie?

---

## 31. Docker Compose

Docker Compose opisuje (w jednym pliku YAML) zestaw kontenerów, które razem tworzą działające środowisko — tu: baza danych + API — wraz z ich zależnościami od siebie.

**Gdzie w repo**: `compose.yaml`.

```yaml
api:
  depends_on:
    db:
      condition: service_healthy
```

To mówi: "nie startuj kontenera `api`, dopóki `db` nie zgłosi się jako zdrowy" (healthcheck).

**Częsty błąd początkującego**: zakładanie, że `depends_on` (bez `condition: service_healthy`) gwarantuje, że baza danych jest już *gotowa do połączeń* — gwarantuje tylko, że kontener się *wystartował*, co nie jest tym samym.

**Pytanie rekrutacyjne**: Co dokładnie robi komenda `python -m scripts.wait_for_db` w `compose.yaml`, i czemu samo `depends_on: condition: service_healthy` mogłoby nie wystarczyć?

---

## 32. CI

CI (Continuous Integration) to automatyczne uruchamianie testów/sprawdzeń przy każdej zmianie kodu (np. każdym pull request), żeby błędy wychwycić zanim trafią do głównej linii kodu.

**Gdzie w repo**: `.github/workflows/ci.yml` — uruchamia PostgreSQL, migracje, `alembic check`, Ruff, mypy, pytest z pokryciem.

```yaml
services:
  postgres:
    image: postgres:16
    ...
```

**Częsty błąd początkującego**: traktowanie CI jako "dodatku", który można pominąć "bo testy przechodzą u mnie lokalnie". CI uruchamia się na czystym, znanym środowisku — wychwytuje właśnie te przypadki, gdzie "u mnie działa" nie znaczy "działa zawsze".

**Pytanie rekrutacyjne**: Dlaczego workflow CI definiuje `JWT_SECRET_KEY` jako zmienną środowiskową na sztywno w pliku YAML, a nie jako sekret pobierany skądś indziej?

---

## 33. Linting

Linter analizuje kod statycznie (bez jego uruchamiania) i wyłapuje potencjalne błędy, nieużywane importy, niezgodność ze stylem.

**Gdzie w repo**: `Ruff` skonfigurowany w `pyproject.toml`.

```bash
ruff check .
```

**Częsty błąd początkującego**: ignorowanie ostrzeżeń lintera za pomocą `# noqa` "żeby uciszyć", bez zrozumienia, *co* dokładnie ostrzeżenie wykrywa. W tym projekcie każdy `# noqa`/`# type: ignore` ma konkretny, jednorazowy powód (i tylko tam, gdzie jest naprawdę potrzebny).

**Pytanie rekrutacyjne**: Jaką realną klasę błędów wykrywa reguła `ASYNC` w Ruff, włączona w tym projekcie?

---

## 34. Formatowanie

Formatter automatycznie ujednolica styl kodu (długość linii, cudzysłowy, odstępy) — eliminuje spory "spacje czy taby" i sprawia, że diff w pull requeście pokazuje tylko *realne* zmiany.

**Gdzie w repo**: `ruff format`, konfiguracja w `pyproject.toml` (`[tool.ruff.format]`).

```bash
ruff format --check .   # tylko sprawdź, nie zmieniaj
ruff format .            # zastosuj formatowanie
```

**Częsty błąd początkującego**: ręczne poprawianie formatowania (spacje, łamanie linii) zamiast po prostu odpalenia formattera. To strata czasu i source niepotrzebnych konfliktów w Git.

**Pytanie rekrutacyjne**: Czym różni się `ruff format --check` używany w CI od `ruff format` używanego lokalnie?

---

## 35. Type checking

Type checking (sprawdzanie typów) statycznie weryfikuje, że typy danych w kodzie się ze sobą zgadzają (np. że nie próbujesz przekazać `str`, gdzie funkcja oczekuje `int`) — bez uruchamiania programu.

**Gdzie w repo**: `mypy`, skonfigurowany w `pyproject.toml` (`[tool.mypy]`), uruchamiany przez `mypy app scripts`.

```python
async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)
```

Jeśli gdzieś w kodzie wywołasz `get_by_id(session, "nie-uuid")`, mypy zgłosi błąd *zanim* kod się uruchomi.

**Częsty błąd początkującego**: pisanie funkcji bez typów (`def get_by_id(session, user_id):`) "bo szybciej". Bez typów mypy nie ma czego sprawdzić — adnotacje typów nie są tu ozdobą, są realnym narzędziem wykrywania błędów.

**Pytanie rekrutacyjne**: `get_settings()` jest opatrzone `@lru_cache`. Jaki typ zwraca, i czemu mypy potrzebuje, żeby `Settings` było poprawnie typowane, by to dobrze zweryfikować?

---

## Pytania kontrolne

1. Jaka jest różnica między `GET /health/live` a `GET /health/ready`?
2. Dlaczego `JWT_SECRET_KEY` nie ma żadnej działającej wartości domyślnej poza środowiskiem testowym?
3. Co dokładnie trafia do tabeli `refresh_token_sessions` przy logowaniu — czy to jest sam token?
4. Czemu `/api/v1/auth/login` przyjmuje dane jako formularz (`application/x-www-form-urlencoded`), a nie JSON, jak inne endpointy?
5. Co się stanie, jeśli wywołasz `/api/v1/auth/refresh` dwa razy z tym samym refresh tokenem?
6. Dlaczego błąd logowania jest identyczny niezależnie od tego, czy e-mail nie istnieje, hasło jest złe, czy konto jest nieaktywne?
7. Jaką rolę odgrywa `hmac.compare_digest` w `rotate_refresh_token` i czemu nie użyto zwykłego `==`?
8. Czym różni się `ConflictError` od `AuthenticationError` — jakie kody HTTP i kiedy zwracają?
9. Dlaczego `app/repositories/*.py` nigdy nie rzucają `HTTPException`?
10. Co robi `session.flush()` w repozytoriach i czym różni się od `session.commit()`?
11. Dlaczego model `Prediction` ma pole `status` z wartością domyślną `PENDING`, mimo że żaden endpoint go jeszcze nie tworzy?
12. Co się stanie, jeśli spróbujesz pobrać `/api/v1/predictions/history` bez tokenu?
13. Dlaczego `PredictionRead` nie ma pola `user_id`?
14. Jak `app/db/session.py` decyduje, z którą bazą danych połączyć się — `medrisk` czy `medrisk_test`?
15. Co konkretnie sprawdza `alembic check` i kiedy zgłosi błąd?
16. Dlaczego w tym projekcie `RequestIdMiddleware` jest "czystym" middleware ASGI, a nie `BaseHTTPMiddleware`?
17. Jaką dokładnie funkcję ma `CASCADE` w `ForeignKey("users.id", ondelete="CASCADE")`?
18. Czym różni się błąd `422` od błędu `401` w tym API — kiedy występuje każdy z nich?
19. Dlaczego testy integracyjne czyszczą bazę danych (`TRUNCATE`) *po* każdym teście, a nie *przed*?
20. Co dokładnie loguje aplikacja, gdy wystąpi nieoczekiwany błąd (500), a czego nigdy nie pokazuje klientowi?
21. Jaka jest różnica między `is_active=False` a usunięciem użytkownika z bazy?
22. Dlaczego `pyproject.toml` zawiera jednocześnie konfigurację Ruff, mypy, pytest i coverage — co by się stało, gdyby każdy z tych narzędzi miał swój osobny plik konfiguracyjny?

## Zadania do samodzielnego wykonania

Każde z poniższych zadań można wykonać bez psowania istniejącej funkcjonalności — przed wysłaniem zmian uruchom `python scripts/check.py`.

1. **Dodaj bezpieczne, opcjonalne pole profilu.** Dodaj do modelu `User` nowe, opcjonalne pole (np. `bio: str | None`, max. 500 znaków). Zrób migrację Alembic, zaktualizuj `UserRead` i napisz test integracyjny sprawdzający, że nowe pole działa.
2. **Dodaj prosty chroniony endpoint.** Np. `GET /api/v1/users/me/summary`, zwracający np. liczbę dni od rejestracji. Wymaga `CurrentUserDep`, własnego schematu odpowiedzi i co najmniej jednego testu integracyjnego.
3. **Napisz nowy test.** Dodaj test integracyjny sprawdzający, że rejestracja z hasłem o długości równo 12 znaków (graniczny przypadek) się powiedzie, a z 11 znakami — nie.
4. **Wyjaśnij migrację.** Otwórz `alembic/versions/..._create_initial_schema.py` i opisz własnymi słowami (np. w komentarzu lub notatce), co konkretnie robi sekcja `downgrade()` z natywnymi enumami PostgreSQL i czemu.
5. **Zajrzyj do payloadu JWT bez ufania mu.** Zaloguj się przez `/api/v1/auth/login`, weź `access_token` i zdekoduj go (np. na jwt.io albo `python -c "import jwt; print(jwt.decode(token, options={'verify_signature': False}))"`). Zapisz, jakie claimy widzisz — i wyjaśnij, czemu mimo że je widzisz, nie możesz ich zmienić i użyć zmienionego tokenu.
6. **Wywołaj i zdiagnozuj błąd walidacji.** Wyślij do `/api/v1/auth/register` żądanie z `email` bez `@`. Zapisz dokładny status code i treść odpowiedzi, i wyjaśnij, który komponent (Pydantic? FastAPI? Twój kod?) wygenerował ten błąd.
7. **Dodaj indeks i zmierz różnicę.** Wybierz zapytanie w `app/repositories/` bez indeksu wspierającego i dodaj go przez migrację Alembic. Uruchom `EXPLAIN ANALYZE` na tym zapytaniu w `psql` przed i po, i zapisz różnicę.
8. **Rozszerz historię predykcji.** Napisz mały skrypt (lub test), który wstawia bezpośrednio przez repozytorium kilka rekordów `Prediction` dla jednego użytkownika z różnymi `created_at`, a potem sprawdza, że `/api/v1/predictions/history?limit=2&offset=0` zwraca je w poprawnej kolejności (najnowsze pierwsze).
