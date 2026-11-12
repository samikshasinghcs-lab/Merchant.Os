"""Compatibility entrypoint; the canonical deployed workflow service is app.render_workflows."""
from app.render_workflows import app

if __name__ == "__main__":
    app.start()
