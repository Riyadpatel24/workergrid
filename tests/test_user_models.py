import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.database import Base
from app.models.user import User, UserGitHubAccount
from app.models.task import Task
from app.models.friction import (
    Repository,
    FrictionAnalysisRun,
    FrictionRawSnapshot,
    FrictionMetric,
    FrictionIndicator,
    FrictionEvidence,
)


class TestUserModels(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_create_user_and_github_account(self):
        """Test User and UserGitHubAccount creation and relationship."""
        user = User(email="testuser@example.com", full_name="Test User", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        self.assertIsNotNone(user.id)
        self.assertEqual(user.email, "testuser@example.com")

        github_account = UserGitHubAccount(
            user_id=user.id,
            github_user_id=12345678,
            github_username="testdev",
            encrypted_access_token="gho_encrypted_secret_token_data",
            scopes="repo,read:user",
        )
        self.db.add(github_account)
        self.db.commit()
        self.db.refresh(user)

        self.assertIsNotNone(user.github_account)
        self.assertEqual(user.github_account.github_username, "testdev")
        self.assertEqual(user.github_account.user.email, "testuser@example.com")

    def test_user_ownership_relationships(self):
        """Test user_id ownership relationships across tasks, repos, and runs."""
        user = User(email="owner@example.com")
        self.db.add(user)
        self.db.commit()

        repo = Repository(user_id=user.id, owner="facebook", name="react", full_name="facebook/react")
        self.db.add(repo)
        self.db.commit()

        task = Task(user_id=user.id, type="test_task", payload={"foo": "bar"})
        run = FrictionAnalysisRun(id="run-user-1", user_id=user.id, repository_id=repo.id)

        self.db.add_all([task, run])
        self.db.commit()

        self.db.refresh(user)
        self.assertEqual(len(user.repositories), 1)
        self.assertEqual(len(user.tasks), 1)
        self.assertEqual(len(user.runs), 1)
        self.assertEqual(user.repositories[0].full_name, "facebook/react")


    def test_legacy_unowned_resources_compatibility(self):
        """Test that unowned resources (user_id=None) are fully supported for backwards compatibility."""
        repo = Repository(owner="pallets", name="flask", full_name="pallets/flask")
        task = Task(type="system_task", payload={})
        run = FrictionAnalysisRun(id="run-legacy-1", repository_id=1)

        self.db.add_all([repo, task, run])
        self.db.commit()

        self.assertIsNone(repo.user_id)
        self.assertIsNone(task.user_id)
        self.assertIsNone(run.user_id)

    def test_per_user_repository_ownership_constraint(self):
        """Test that two different users can analyze/own the same repository full_name."""
        user1 = User(email="user1@example.com")
        user2 = User(email="user2@example.com")
        self.db.add_all([user1, user2])
        self.db.commit()

        repo1 = Repository(user_id=user1.id, owner="fastapi", name="fastapi", full_name="fastapi/fastapi")
        repo2 = Repository(user_id=user2.id, owner="fastapi", name="fastapi", full_name="fastapi/fastapi")
        self.db.add_all([repo1, repo2])
        self.db.commit()

        self.assertNotEqual(repo1.id, repo2.id)
        self.assertEqual(repo1.full_name, repo2.full_name)
        self.assertEqual(repo1.user_id, user1.id)
        self.assertEqual(repo2.user_id, user2.id)

    def test_duplicate_user_email_raises_error(self):
        """Test that duplicate email addresses trigger an IntegrityError."""
        u1 = User(email="dupe@example.com")
        u2 = User(email="dupe@example.com")
        self.db.add(u1)
        self.db.commit()

        self.db.add(u2)
        with self.assertRaises(IntegrityError):
            self.db.commit()


if __name__ == "__main__":
    unittest.main()
