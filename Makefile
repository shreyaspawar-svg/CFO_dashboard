.PHONY: dev backend frontend test

# One-command start for local (non-Docker) development. Requires the
# backend venv already created (see README "Running the backend locally")
# and frontend deps already installed (`npm install` in frontend/).
dev:
	@echo "Starting backend (http://localhost:8000) and frontend (http://localhost:3000)..."
	@(cd backend && ./.venv/Scripts/uvicorn app.main:app --reload &) 2>/dev/null || (cd backend && .venv/bin/uvicorn app.main:app --reload &)
	@(cd frontend && npm run dev &)
	@echo "Ctrl-C won't stop the background processes on Windows -- see README for how to stop them."

backend:
	cd backend && ./.venv/Scripts/uvicorn app.main:app --reload

frontend:
	cd frontend && npm run dev

test:
	cd backend && ./.venv/Scripts/pytest
	cd frontend && npm test -- --run
