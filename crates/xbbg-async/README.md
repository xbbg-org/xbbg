# xbbg-async

Async worker-pool engine over `xbbg-core` for Bloomberg API requests and subscriptions.

## Architecture

```
Engine
├── RequestWorkerPool        (round-robin dispatch, default 2 workers)
│   └── Worker threads       each owns a Session + Slab<UnifiedRequestState>
│       └── 12 state machines: RefData, HistData, BulkData, IntradayBar,
│           IntradayTick, HistDataStream, IntradayBarStream,
│           IntradayTickStream, Generic, Bql, Bsrch, FieldInfo
├── SubscriptionSessionPool  (claim/release, default 4 sessions)
│   └── Sub-worker threads   each owns a Session + Slab<SubscriptionState>
├── SchemaCache              (in-memory + disk-persisted service schemas)
├── FieldCache               (global, disk-persisted field type resolution)
└── Tokio Runtime
```

Each worker thread owns its own Bloomberg `Session` — no `Arc<Session>`, no shared
state, no contention.  Requests are dispatched round-robin across the pool;
subscriptions are claimed from a separate session pool.

## Key modules

| Module | Purpose |
|--------|---------|
| `engine/` | Engine startup, shutdown, command dispatch |
| `engine/worker/` | Per-worker event loop and request lifecycle |
| `engine/sub_worker/` | Per-session subscription event loop |
| `engine/state/` | 12 state machines for different Bloomberg operations |
| `schema/` | Service schema introspection + disk cache |
| `field_cache.rs` | Global field-type resolver with disk persistence |
| `errors.rs` | `BlpAsyncError` — async-layer error type |

## Design decisions

- **One Session per thread** — Bloomberg's `Session` is not `Sync`.  Rather than
  wrapping it in a `Mutex`, each worker owns its session outright, eliminating
  contention entirely.
- **Slab-based correlation** — In-flight requests are tracked with a `Slab`,
  giving O(1) insert/remove and compact memory layout.
- **Schema + field caching** — Service schemas and field metadata are cached to
  disk, avoiding repeated introspection on startup.
