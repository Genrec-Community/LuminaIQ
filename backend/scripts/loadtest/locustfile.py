"""
Load test for the API paths that don't need AI keys.

Each simulated user gets its own sign-in token (signed with the dev SECRET_KEY,
so only run this against a dev/test server), creates a book, then browses it.

    cd backend
    LOADTEST_SECRET_KEY=<SECRET_KEY of the target> uvx --with python-jose locust \
        -f scripts/loadtest/locustfile.py --host http://localhost:8000 \
        --headless -u 200 -r 20 -t 60s
"""

import os
import uuid

from jose import jwt
from locust import HttpUser, between, task

SECRET = os.environ.get("LOADTEST_SECRET_KEY", "")


class Student(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self):
        if not SECRET:
            raise RuntimeError("Set LOADTEST_SECRET_KEY to the target server's SECRET_KEY")
        uid = str(uuid.uuid4())
        token = jwt.encode({"sub": uid, "email": f"load-{uid[:8]}@example.com"}, SECRET, algorithm="HS256")
        self.client.headers.update({"Authorization": f"Bearer {token}"})
        res = self.client.post("/api/v1/projects/", json={"name": "Load test book"}, name="POST /projects")
        self.project_id = res.json()["id"]

    @task(4)
    def projects(self):
        self.client.get("/api/v1/projects/", name="GET /projects")

    @task(3)
    def open_book(self):
        self.client.get(f"/api/v1/projects/{self.project_id}", name="GET /projects/:id")
        self.client.get(f"/api/v1/documents/{self.project_id}", name="GET /documents/:project")

    @task(3)
    def chat_history(self):
        self.client.get(f"/api/v1/chat/history/{self.project_id}", name="GET /chat/history/:project")

    @task(2)
    def settings_and_xp(self):
        self.client.get("/api/v1/user-data/settings", name="GET /user-data/settings")
        self.client.get("/api/v1/user-data/gamification", name="GET /user-data/gamification")

    @task(1)
    def bookmark(self):
        self.client.post("/api/v1/user-data/bookmarks",
                         json={"project_id": self.project_id, "title": "Key idea"}, name="POST /bookmarks")
        self.client.get(f"/api/v1/user-data/bookmarks/{self.project_id}", name="GET /bookmarks/:project")
