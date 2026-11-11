# Google Keep Clone API

An asynchronous FastAPI and PostgreSQL implementation of a Google Keep-style
notes application. The project supports text notes, checklist notes, image
references, tags, note filtering, full-text-search-ready storage, JWT
authentication, and load testing with Locust.

This project was built as more than a CRUD exercise. It focuses on the
engineering decisions behind a maintainable API: modeling related data,
protecting every user-owned resource, using asynchronous database access,
measuring system behavior under load, and finding the point where the API
becomes CPU-bound.

## What the application does

Users can:

- Register and authenticate with a username or email.
- Receive a JWT access token after login.
- Create text, checklist, and image-reference notes.
- Add tags to notes.
- Read, update, and permanently delete notes.
- Archive, pin, or trash notes through note state fields.
- Filter notes by tag and state.
- Search through the PostgreSQL search vector column.
- Retrieve and manage their own tags.
- Delete their account and its owned notes, checklist items, tags, and
  note-tag relationships through the current logout/delete route.

Every user-owned query is scoped through the authenticated user's ID. A client
cannot choose an arbitrary user ID and use it to access another user's notes
or tags.

## Technology stack

- **Python 3.12**
- **FastAPI** for HTTP routing and request validation
- **Pydantic** for request and response schemas
- **SQLAlchemy 2.0 async ORM**
- **asyncpg** for asynchronous PostgreSQL access
- **PostgreSQL 15**
- **Alembic** for schema migration history
- **PyJWT** for access tokens
- **bcrypt** for password hashing
- **Locust** for load testing
- **Docker Compose** for local PostgreSQL and API orchestration
- **pytest and HTTPX** for asynchronous API tests

## Project structure

```text
.
├── app/
│   ├── main.py                 # FastAPI application and lifespan
│   ├── config.py               # Environment-backed settings
│   ├── db.py                   # Async SQLAlchemy engine and sessions
│   ├── models.py               # User, note, checklist, tag, and join models
│   ├── logs.py                 # JSON logging configuration
│   ├── locustfile.py           # Weighted Locust workload
│   ├── routes/
│   │   ├── auth.py             # Registration, login, authentication, deletion
│   │   ├── notes.py            # Note and checklist operations
│   │   └── tags.py             # Tag operations
│   ├── alembic/                # Migration environment and revisions
│   └── test/                   # Async API tests
├── scripts/
│   └── seed_data.py            # Local-only load-test data generator
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── alembic.ini
├── guide.md
└── README.md
```

The seed utility is explicitly excluded from the Docker build context through
`.dockerignore`. It is intended for local performance testing, not production
deployment.

## Running locally

### Prerequisites

- Python 3.12 or newer
- Docker Desktop
- Docker Compose
- PostgreSQL client tools are optional

### Environment configuration

Create a `.env` file. A local configuration typically resembles:

```env
DB_URL=postgresql+asyncpg://myuser:mypassword@localhost:5432/keep_clone_db
TEST_DB_URL=postgresql+asyncpg://myuser:mypassword@localhost:5432/test_db
SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

When the API runs inside Docker Compose, the PostgreSQL hostname is the
Compose service name, usually `postgres`. When a script runs directly on the
Windows host, the database hostname must normally be `localhost`.

### Start PostgreSQL

```powershell
docker compose up -d postgres
```

### Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Run the API

```powershell
uvicorn app.main:app --reload
```

The API is available at:

```text
http://localhost:8000
```

Interactive API documentation is available at:

```text
http://localhost:8000/docs
```

### Run with Docker Compose

```powershell
docker compose up --build
```

For production-like deployments, migrations should be run as an explicit
deployment step instead of relying on application startup schema creation:

```powershell
alembic upgrade head
```

## API overview

### Authentication

```text
POST   /auth/register
POST   /auth/login
DELETE /auth/logout
```

The current `DELETE /auth/logout` endpoint removes the authenticated user's
account and owned data. It is therefore closer to an account-deletion endpoint
than a conventional session logout. A future version should separate ordinary
token/session revocation from permanent account deletion.

### Notes

```text
GET    /notes/
GET    /notes/{note_id}
POST   /notes/
PATCH  /notes/{note_id}
DELETE /notes/{note_id}
```

The notes list supports pagination and filters for archived, trashed, pinned,
tag, and search values. Note responses can include tags and checklist items.

### Tags

```text
GET    /tags/
POST   /tags/
PATCH  /tags/{tag_id}
DELETE /tags/{tag_id}
```

## Data model

```text
users
  id, username, email, password, created_at

notes
  id, user_id, title, body, color, note_type, image_url
  is_archived, is_trashed, is_pinned, trashed_at
  created_at, updated_at, search_vector

checklist_items
  id, note_id, content, is_checked, created_at, updated_at

tags
  id, user_id, name, created_at, updated_at

note_tag
  note_id, tag_id
```

The `notes` table uses a `note_type` discriminator rather than separate tables
for text, checklist, and image notes. This keeps the main feed unified while
allowing checklist-specific data to live in `checklist_items`.

Tags use a many-to-many association table because a note can have multiple
tags and a tag can belong to multiple notes. This is more expressive than
storing comma-separated tag names in a note column and allows association
queries to remain relational.

## Local load-test data

The local-only script creates 50 deterministic users:

```text
loadtest_001 through loadtest_050
```

Each user receives:

- A bcrypt-hashed password
- Three notes
- One checklist note with populated checklist items
- Image-note metadata
- Two tags
- Note-tag associations

The default password for the seeded users is:

```text
LoadtestPassword123
```

Create the data:

```powershell
.\.venv\Scripts\python.exe scripts\seed_data.py
```

Delete only the seeded users and their related records:

```powershell
.\.venv\Scripts\python.exe scripts\seed_data.py --delete
```

If the database URL in `.env` uses the Docker hostname `postgres`, the script
automatically changes that hostname to `localhost` for a host-side run. An
explicit URL can also be supplied:

```powershell
.\.venv\Scripts\python.exe scripts\seed_data.py `
  --db-url "postgresql+asyncpg://myuser:mypassword@localhost:5432/keep_clone_db"
```

## Locust workload

The Locust scenario logs in each virtual user during `on_start()` using the
seeded accounts. It does not register or delete accounts during the steady
state workload. The seeded account pool can be reused when the number of
virtual users exceeds 50, which is useful for API stress testing.

The steady-state task weights are:

| Route | Weight | Purpose |
|---|---:|---|
| `GET /notes/` | 50 | Main notes feed |
| `GET /notes/{id}` | 20 | Open a note |
| `POST /notes/` | 15 | Create a note |
| `PATCH /notes/{id}` | 10 | Edit a note |
| `GET /tags/` | 5 | Load tags |

Run a headless test:

```powershell
.\.venv\Scripts\locust.exe `
  -f app\locustfile.py `
  --headless `
  -H http://localhost:8000 `
  -u 100 `
  -r 10 `
  -t 5m
```

The `-u` option controls concurrent virtual users and `-r` controls the spawn
rate. More virtual users do not automatically mean more throughput: once the
API CPU is saturated, extra users primarily increase waiting and tail latency.

## Scalability and performance

### What was measured

The load tests were run locally against the API and PostgreSQL containers.
The results below are benchmark observations for this machine and this
workload, not universal capacity guarantees.

### 10 November: initial, unoptimized workload

The initial test produced approximately:

```text
Throughput: approximately 24 requests/sec
Users:      50
Failures:   0%
```

The main limitation was the original Locust pacing and lifecycle design. Each
virtual user waited much longer between requests, so the load generator was
not applying enough pressure to the API to measure its actual steady-state
capacity.

### 11 November: revised workload, 50 users

The Locust workload was changed to:

- Use pre-seeded users instead of registering during the workload.
- Log in once during user startup.
- Use weighted steady-state note and tag operations.
- Reduce the wait interval so the load generator could reach the API limit.
- Avoid requesting a note with a missing ID.
- Reuse a controlled pool of seeded users for higher concurrency tests.

The 50-user report measured approximately:

```text
Total requests: 30,061
Throughput:     117.78 requests/sec
Failures:       0
Average:        288.9 ms
Median:         230 ms
95th percentile: 740 ms
99th percentile: 1,200 ms
Maximum:        8,258 ms
```

The route-level distribution was:

```text
GET /notes/       58.88 req/sec
GET /notes/{id}   22.76 req/sec
POST /notes/      18.05 req/sec
PATCH /notes/{id} 12.04 req/sec
GET /tags/         5.85 req/sec
```

There were 50 login requests, with an average login time of approximately
2.65 seconds. That cost is expected from bcrypt and occurred only during
startup; it was not a major part of the steady-state request rate.

### 11 November: revised workload, 100 users

The 100-user run produced approximately the same throughput, around
118–120 requests/sec, with no failures. This is an important result:
increasing concurrency did not materially increase throughput because the API
container was already CPU-bound.

During these runs, the observed average resource usage was approximately:

```text
API container CPU: around 99%
PostgreSQL CPU:    around 28%
Failures:          0%
```

The database still had available CPU while the API process was saturated. The
median latency remained much lower than the tail latency, which showed that
additional concurrency was more likely to increase queueing and p95/p99
latency than to produce proportionally more requests per second.

### Interpreting Docker CPU percentages

Docker reports CPU usage relative to one logical CPU. For example:

```text
128% / 1600%
```

means approximately 1.28 CPU cores used out of 16 logical CPU cores visible to
Docker. It does not mean the container used 128% of the entire machine.

The useful question is whether the aggregate host, API containers, database,
memory, and disk remain healthy—not whether one container's percentage is
below 100%.

### Ten-container scaling hypothesis

One API container achieved approximately 118 requests/sec before its CPU
became the limiting resource. If ten independent API containers were placed
behind a reverse proxy, a simple linear estimate would be:

```text
1 container  ≈ 118 req/sec
10 containers ≈ 1,180 req/sec theoretical estimate
```

This does not mean 1,180 requests/sec has already been achieved. It is a
scaling target that depends on the laptop having enough CPU and memory and
PostgreSQL handling the shared workload. A real result could be materially
lower because all replicas still share:

- Host CPU and memory
- PostgreSQL
- Database connections
- Disk and network resources
- Docker networking
- Reverse-proxy overhead

The correct experiment is to measure one, two, four, eight, and ten replicas
using the same Locust profile. A reverse proxy/load balancer is required; a
forward proxy is not the appropriate component for routing client traffic to
API replicas.

## Engineering decisions

### Asynchronous database access

The API uses SQLAlchemy's asynchronous engine and `asyncpg`. Route handlers
await database operations instead of blocking the event loop while waiting
for PostgreSQL. This allows the FastAPI process to continue servicing other
requests during I/O waits.

The session dependency creates an `AsyncSession` per request and closes it
through the async context manager. The engine uses connection pooling,
pre-ping, and connection recycling to reduce failures caused by stale
connections.

### Authentication and password security

Passwords are never stored in plaintext. Registration hashes passwords with
bcrypt, and login verifies the submitted password against the stored bcrypt
hash.

Successful login produces a signed JWT containing the authenticated user's
identity. Protected routes use the bearer-token dependency, decode and verify
the token, then load the user from the database.

The secret key and token configuration are environment-driven. Production
deployments must use a strong secret that is not committed to source control.

JWT access tokens are intentionally stateless in the current design. A future
session or refresh-token system should be introduced if immediate revocation,
device management, or ordinary logout is required.

### Avoiding the N+1 query problem

The notes list and detail queries use SQLAlchemy `selectinload` for tags and
checklist items. This loads related collections in predictable additional
queries rather than triggering one query per note during response
serialization.

This is especially important for a notes feed: without eager loading, a page
of notes could cause a query for every note's tags and every note's checklist
items. The current strategy keeps the query count bounded by relationship
type rather than result count.

### Query and response design

The note queries scope records by `user_id` before returning data. Filters for
archived, trashed, pinned, tag, and search values are applied to the database
query rather than filtering a larger result set in Python.

The Locust workload also records note IDs returned by the list endpoint and
uses them for detail and update requests. This avoids generating invalid
`/notes/None` requests and makes the workload represent real user behavior.

### Transactions and cleanup

Create, update, and delete operations commit as transactions and roll back
when database errors occur. The account deletion route removes association
rows and dependent records before deleting the user, respecting the current
foreign-key structure.

The seed utility uses the same principle: it removes only users with the
`loadtest_` prefix and deletes their note-tag links, checklist items, notes,
tags, and user records. Production users are not part of that cleanup scope.

### Validation and API boundaries

Pydantic models validate required fields, string lengths, note types, image-note
requirements, checklist requirements, and note state combinations before route
logic runs. This keeps malformed input from reaching database operations and
keeps route handlers focused on application behavior.

### Monitoring and logging

The application uses structured JSON logging with timestamps, levels, logger
names, messages, and exception details. This format is easier to ingest into a
log collector than unstructured print output.

Database failures, authentication failures, registration failures, and route
errors are logged with context such as user IDs and resource IDs. SQLAlchemy
logging can be enabled during local debugging to inspect generated queries,
but verbose SQL logging should be controlled in production because it creates
significant output and can expose sensitive query details.

Locust reports provide another monitoring layer:

- Requests per second
- Failure count
- Average and median latency
- p95 and p99 latency
- Maximum latency
- Route-level request distribution

The most useful performance signal is not throughput alone. A system that
reports high requests/sec while p99 latency and failures rise is not scaling
successfully.

## Problems solved during development

This project became a practical exercise in diagnosing real integration
problems rather than only implementing the happy path. Each issue was reduced
to a concrete boundary, tested, and fixed at the source.

### Docker networking versus host networking

The API and PostgreSQL containers use the Compose service hostname
`postgres`. That hostname is valid inside the Docker network but cannot be
resolved when a Python utility is executed directly from Windows. The seed
script initially failed with `socket.gaierror: [Errno 11001] getaddrinfo
failed`.

The solution was to distinguish execution environments instead of changing
the container configuration blindly. The seed script reads the configured
database URL, translates the Docker-only hostname to `localhost` for a
host-side run, and also accepts an explicit `--db-url` override. The same
configuration can therefore work inside Compose and from the developer
machine without hiding the actual networking boundary.

### Dependency and interpreter diagnosis

The first direct invocation used the system Python and reported that
`asyncpg` was unavailable. The project virtual environment already contained
the dependency. Rather than modifying application code or installing packages
randomly, the command was rerun with the project's `.venv` interpreter. This
separated a missing-environment problem from a code problem and produced a
successful end-to-end seed run.

### Safe Locust lifecycle design

The load test originally mixed registration, login, token storage, and
deletion in global state. That introduced correctness risks: a token removed
from a shared list was not guaranteed to belong to the Locust user stopping at
that moment. The workload was simplified so seeded users are prepared once,
each virtual user logs in during `on_start()`, and steady-state tasks focus on
the application routes being measured.

This matters because a benchmark must measure the intended workload. Account
registration, bcrypt hashing, and account deletion are useful separate tests,
but including them in the normal notes workload would distort the result.

### Foreign-key-aware deletion

Deleting a user is not just deleting one row. Notes, checklist items, tags,
and note-tag associations depend on one another. Cleanup was implemented in
dependency order so association and child rows are removed before the user.
The same approach is used by the local seed reset function, which is scoped to
the load-test username prefix and cannot intentionally remove unrelated users.

### Moving from a load-generator bottleneck to an API bottleneck

The initial test produced only about 24 requests/sec because the Locust users
waited too long between actions. The test was redesigned with seeded data,
login-on-start, weighted tasks, valid note-ID reuse, and shorter configurable
wait intervals. That exposed the actual API behavior: approximately
118 requests/sec with no failures and API CPU near saturation.

The 50-user and 100-user runs then produced essentially the same throughput.
That result was not treated as a failed test. It identified the next boundary:
the API process had reached its CPU ceiling while PostgreSQL still had spare
capacity. This is the kind of conclusion a benchmark should provide—evidence
about the next bottleneck, not just a larger number on a dashboard.

## Future performance improvements

The current benchmark identifies several logical next steps:

1. **Run multiple API workers or replicas.**  
   Test one, two, four, eight, and ten replicas behind a reverse proxy. Size
   database pools based on the total number of processes rather than per
   container alone.

2. **Add and verify indexes.**  
   Index frequently filtered foreign keys such as `notes.user_id`,
   `checklist_items.note_id`, `tags.user_id`, and both `note_tag` columns.
   Use `EXPLAIN ANALYZE` with realistic data before and after each index.

3. **Add a GIN index for full-text search.**  
   The generated `search_vector` is useful only at scale if PostgreSQL can
   use an appropriate index for the search predicate.

4. **Replace deep offset pagination with cursor pagination.**  
   Offset pagination becomes more expensive as the offset grows. A cursor
   based on `updated_at` and `id` can keep feed queries stable.

5. **Create lightweight list responses.**  
   The feed does not always need the complete note body, checklist, and tag
   payload. A compact list representation would reduce database transfer,
   serialization cost, and response size.

6. **Batch tag lookups.**  
   Note creation and updates currently check tags inside loops. Fetching
   existing tags in one query and creating missing tags in bulk would reduce
   round trips.

7. **Separate account deletion from logout.**  
   A normal logout should revoke a session or refresh token. Permanent user
   deletion should be an explicit account-deletion operation.

8. **Run Alembic migrations explicitly.**  
   Schema creation at application startup is convenient for development but
   creates race and ownership problems when multiple API replicas start.

9. **Measure before tuning connection pools.**  
   More connections do not always mean more throughput. Pool size should be
   chosen from PostgreSQL capacity, replica count, and observed pool wait
   time.

10. **Add production metrics and tracing.**  
    Request duration histograms, database pool metrics, active connections,
    error counters, and distributed tracing would make bottlenecks visible
    without relying only on a load-test report.

11. **Use a background worker for non-critical work.**  
    Image processing, reminder delivery, cleanup of old trash, and other
    slow side effects should not block the request path once those features
    are introduced.

12. **Introduce caching only after profiling.**  
    Redis could help with session revocation, frequently read tags, or hot
    feeds, but it should be added because measurements justify it—not because
    every scalable architecture includes a cache.

## What this project demonstrates

This project demonstrates a complete engineering loop:

1. Model a real domain with users, notes, checklists, tags, and associations.
2. Validate input at the API boundary.
3. Protect resources with authenticated, user-scoped queries.
4. Use bcrypt and JWTs for the initial authentication design.
5. Use asynchronous database access for concurrent I/O.
6. Avoid accidental N+1 relationship loading with eager-loading options.
7. Handle transaction failures with rollback and explicit error responses.
8. Build deterministic local data for repeatable load tests.
9. Measure throughput, latency percentiles, and failures instead of guessing.
10. Use the measurements to identify whether the load generator, API, or
    database is the current bottleneck.
11. Understand that horizontal scaling is a measured experiment, not a
    promise made by adding containers.

The most important result is not the claim that the application can reach a
particular number of requests per second on every machine. The important
result is that the system was made measurable, the workload was made more
representative, and the bottleneck was identified with evidence. From there,
additional workers, replicas, indexes, pagination changes, and database
tuning can be evaluated one controlled change at a time.

