# FireSight Repository Layout

The repository separates three independently deployable runtimes: the FastAPI backend, the Vite dashboard, and ESP32 firmware. This keeps platform-specific build tools isolated while retaining one versioned API contract and one issue/CI history.

`apps/` contains deployable applications. `packages/` contains only code or contracts with more than one consumer. Start a module inside the application that owns it; promote it into `packages/` only after another application genuinely needs it.

The backend follows a `src/` layout so imports are tested from the installed package rather than accidentally from the working directory. Its layers have one-way dependencies:

```text
api routes -> services -> domain
                   |        |
                   v        v
             infrastructure  schemas/contracts
```

Infrastructure adapters (camera, detector, storage, notification) belong behind service interfaces. The decision engine must remain free of HTTP, database, and camera I/O so it can be tested with deterministic clocks and inputs.

The ESP32 application is a standalone PlatformIO project. PlatformIO conventionally keeps C++ sources in `src/`, headers in `include/`, project-local reusable libraries in `lib/`, and hardware tests in `test/`.

References: [Turborepo internal packages](https://turborepo.dev/docs/crafting-your-repository/creating-an-internal-package), [Nx folder structure](https://nx.dev/concepts/decisions/folder-structure/), and [PlatformIO library structure](https://docs.platformio.org/en/latest/librarymanager/creating.html).
