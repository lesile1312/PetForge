# Development

Install Node.js 20+, pnpm, Python 3.11+, and Godot 4.3+ on Windows. From the repository root, install the JavaScript and Python dependencies as listed in the README, then run `pnpm dev` to start both services. Environment values are documented in `.env.example`.

The Web app uses port 3000 and the API uses 8000. Set `NEXT_PUBLIC_API_URL` when changing the API origin. Set `PETFORGE_GODOT_EXECUTABLE` and `PETFORGE_RUNTIME_PROJECT` for desktop launch. The Godot project also opens independently from the editor; package path is passed as a command-line user argument.

Generated image files and SQLite data live under the repository-root `storage/` directory during development. `PETFORGE_STORAGE_ROOT` and `PETFORGE_DATABASE_PATH` can override those paths. Do not put secrets into `.env.example` or commit `.env`.
