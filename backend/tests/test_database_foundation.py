import importlib.util
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import alembic.context as alembic_context
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import HTTPException
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.sql.elements import conv

from app import attempts, auth, database, exams, users
from app.attempts.models import AttemptQuestion, ExamAttempt, StudentAnswer
from app.auth import (
    ROLE_ADMIN,
    ROLE_STUDENT,
    AuthIdentity,
    require_admin,
    require_identity,
    require_student,
)
from app.config import ConfigurationError, Settings, get_settings
from app.database import (
    Base,
    dispose_engine,
    get_engine,
    get_session_factory,
    normalize_postgres_url,
)
from app.database.session import _postgres_connect_args
from app.exams.models import Exam, Question, QuestionOption
from app.users.models import ApplicationUser


@contextmanager
def _isolated_sqlite_session_factory(
    db_path: Path,
) -> Iterator[tuple[sa.Engine, object]]:
    """Provision a clean SQLite test database with PRAGMA foreign_keys=ON."""
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{db_path.as_posix()}",
    )
    engine = get_engine(settings)
    factory = get_session_factory(settings)
    Base.metadata.create_all(engine)
    try:
        yield engine, factory
    finally:
        dispose_engine()


def _seed_admin_and_exam(db: Session) -> tuple[ApplicationUser, ApplicationUser, Exam, Question]:
    admin = ApplicationUser(
        id=uuid4(),
        auth_subject="sub-admin-1",
        email="admin@example.edu",
        display_name="Admin One",
        role=ROLE_ADMIN,
    )
    student = ApplicationUser(
        id=uuid4(),
        auth_subject="sub-student-1",
        email="student@example.edu",
        display_name="Student One",
        role=ROLE_STUDENT,
    )
    db.add_all([admin, student])
    db.flush()

    exam = Exam(
        id=uuid4(),
        title="Midterm Biology",
        duration_minutes=45,
        max_attempts=2,
        status="PUBLISHED",
        created_by=admin.id,
    )
    db.add(exam)
    db.flush()

    question = Question(
        id=uuid4(),
        exam_id=exam.id,
        question_text="What is the powerhouse of the cell?",
        position=1,
    )
    db.add(question)
    db.flush()
    return admin, student, exam, question


def test_domain_foundation_packages_import_cleanly() -> None:
    assert hasattr(auth, "AuthIdentity")
    assert hasattr(auth, "require_identity")
    assert hasattr(auth, "require_student")
    assert hasattr(auth, "require_admin")
    assert auth.ROLE_ADMIN == "ADMIN"
    assert auth.ROLE_STUDENT == "STUDENT"
    assert not hasattr(auth, "UserRole")
    assert hasattr(users, "__doc__")
    assert hasattr(exams, "__doc__")
    assert hasattr(attempts, "__doc__")
    assert hasattr(database, "Base")
    assert ApplicationUser.__tablename__ == "application_users"
    assert Exam.__tablename__ == "exams"
    assert Question.__tablename__ == "questions"
    assert QuestionOption.__tablename__ == "question_options"
    assert ExamAttempt.__tablename__ == "exam_attempts"
    assert ExamAttempt.__table__.c.submission_reason.type.length >= len("STUDENT_SUBMITTED")
    assert AttemptQuestion.__tablename__ == "attempt_questions"
    assert StudentAnswer.__tablename__ == "student_answers"


def test_auth_boundary_requires_a_bearer_token_and_enforces_db_roles(
    tmp_path: Path,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_identity(credentials=None, settings=Settings(_env_file=None))
    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    with _isolated_sqlite_session_factory(tmp_path / "auth_boundary.db") as (_engine, factory):
        with factory() as db:
            # Unprovisioned identity fails closed on require_admin (401)
            unknown_identity = AuthIdentity(
                subject="unprovisioned-sub",
                email="nobody@example.edu",
                name="Nobody",
            )
            with pytest.raises(HTTPException) as admin_unprovisioned_exc:
                require_admin(identity=unknown_identity, db=db)
            assert admin_unprovisioned_exc.value.status_code == 401

            # require_student auto-provisions default STUDENT role and returns DB user_id
            student_identity = require_student(
                identity=AuthIdentity(
                    subject="fresh-student-sub",
                    email="fresh@example.edu",
                    name="Fresh Student",
                ),
                db=db,
            )
            assert student_identity.role == ROLE_STUDENT
            assert isinstance(student_identity.user_id, UUID)

            # Student cannot satisfy require_admin (403)
            with pytest.raises(HTTPException) as student_as_admin_exc:
                require_admin(identity=student_identity, db=db)
            assert student_as_admin_exc.value.status_code == 403

            # DB-promoted ADMIN passes require_admin and is rejected by require_student (403)
            admin_user = ApplicationUser(
                id=uuid4(),
                auth_subject="promoted-admin-sub",
                email="boss@example.edu",
                display_name="Boss Admin",
                role=ROLE_ADMIN,
            )
            db.add(admin_user)
            db.commit()

            admin_raw_identity = AuthIdentity(
                subject="promoted-admin-sub",
                email="boss@example.edu",
                name="Boss Admin",
            )
            resolved_admin = require_admin(identity=admin_raw_identity, db=db)
            assert resolved_admin.role == ROLE_ADMIN
            assert resolved_admin.user_id == admin_user.id

            with pytest.raises(HTTPException) as admin_as_student_exc:
                require_student(identity=admin_raw_identity, db=db)
            assert admin_as_student_exc.value.status_code == 403


def test_normalize_postgres_url_rewrites_driver_and_preserves_encoded_password() -> None:
    raw = (
        "postgres://neon_user:p%40ss%2Fword"
        "@ep-cool-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
    )
    normalized = normalize_postgres_url(raw)

    assert normalized.drivername == "postgresql+psycopg"
    rendered = normalized.render_as_string(hide_password=False)
    assert rendered.startswith("postgresql+psycopg://neon_user:p%40ss%2Fword@")
    assert "sslmode=require" in rendered


def test_sqlalchemy_base_naming_convention_and_timezone_aware_datetime() -> None:
    class _FoundationParent(Base):
        __tablename__ = "_foundation_parent"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        created_at: Mapped[datetime]

    class _FoundationChild(Base):
        __tablename__ = "_foundation_child"
        __table_args__ = (
            UniqueConstraint("parent_id", "position", name=None),
            CheckConstraint("position >= 0", name="position_nonneg"),
            CheckConstraint("position < 1000", name="_foundation_child_max"),
            CheckConstraint(
                "position != 999",
                name="ck__foundation_child_not_999",
            ),
            CheckConstraint(
                "position != 998",
                name=conv("ck__foundation_child_explicit"),
            ),
        )
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        parent_id: Mapped[int] = mapped_column(ForeignKey("_foundation_parent.id"))
        position: Mapped[int]

    try:
        assert _FoundationParent.__table__.c.created_at.type.timezone is True
        constraint_names = {c.name for c in _FoundationChild.__table__.constraints}
        assert "uq__foundation_child_parent_id_position" in constraint_names
        assert "pk__foundation_child" in constraint_names
        assert "fk__foundation_child_parent_id__foundation_parent" in constraint_names
        assert "ck__foundation_child_position_nonneg" in constraint_names
        assert "ck__foundation_child_not_999" in constraint_names
        assert "ck__foundation_child_explicit" in constraint_names
        assert "ck__foundation_child_ck__foundation_child_not_999" not in constraint_names
    finally:
        Base.metadata.remove(_FoundationChild.__table__)
        Base.metadata.remove(_FoundationParent.__table__)


def test_base_metadata_resolves_complete_application_schema_without_double_prefixes() -> None:
    expected_tables = {
        "application_users",
        "exams",
        "questions",
        "question_options",
        "exam_source_files",
        "exam_attempts",
        "attempt_questions",
        "student_answers",
    }
    assert set(Base.metadata.tables.keys()) == expected_tables

    exams_table = Base.metadata.tables["exams"]
    assert exams_table.c.closed_at.nullable is True
    assert exams_table.c.closed_at.type.timezone is True

    uuid_columns = [
        ("application_users", "id"),
        ("exams", "id"),
        ("exams", "created_by"),
        ("questions", "id"),
        ("questions", "exam_id"),
        ("question_options", "id"),
        ("question_options", "question_id"),
        ("exam_attempts", "id"),
        ("exam_attempts", "exam_id"),
        ("exam_attempts", "user_id"),
        ("attempt_questions", "attempt_id"),
        ("attempt_questions", "question_id"),
        ("student_answers", "id"),
        ("student_answers", "attempt_id"),
        ("student_answers", "question_id"),
        ("student_answers", "selected_option_id"),
    ]
    for table_name, col_name in uuid_columns:
        col_type = Base.metadata.tables[table_name].c[col_name].type
        assert isinstance(col_type, sa.Uuid), f"{table_name}.{col_name} must be sa.Uuid"
        assert col_type.as_uuid is True

    for table in Base.metadata.tables.values():
        assert table.schema != "neon_auth"
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint):
                assert constraint.name is not None
                assert constraint.name.startswith(f"ck_{table.name}_")
                assert not constraint.name.startswith(f"ck_{table.name}_ck_")


def test_alembic_include_object_excludes_neon_auth_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini = backend_dir / "alembic.ini"
    alembic_env_path = backend_dir / "alembic" / "env.py"

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://placeholder:placeholder@ep-direct.us-east-1.aws.neon.tech/neondb?sslmode=require",
    )
    get_settings.cache_clear()

    configured_kwargs: dict[str, object] = {}
    monkeypatch.setattr(alembic_context, "config", Config(str(alembic_ini)), raising=False)
    monkeypatch.setattr(alembic_context, "is_offline_mode", lambda: True, raising=False)
    monkeypatch.setattr(
        alembic_context,
        "configure",
        lambda **kwargs: configured_kwargs.update(kwargs),
        raising=False,
    )
    monkeypatch.setattr(
        alembic_context,
        "begin_transaction",
        lambda: nullcontext(),
        raising=False,
    )
    monkeypatch.setattr(alembic_context, "run_migrations", lambda: None, raising=False)

    try:
        spec = importlib.util.spec_from_file_location("local_alembic_env", alembic_env_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        include_object = configured_kwargs["include_object"]
        neon_meta = MetaData()
        neon_users = Table("users_sync", neon_meta, Column("id", Integer), schema="neon_auth")
        public_meta = MetaData()
        app_users = Table("application_users", public_meta, Column("id", Integer))

        assert include_object(neon_users, "users_sync", "table", True, None) is False
        assert include_object(neon_users.c.id, "id", "column", True, None) is False
        assert include_object(app_users, "application_users", "table", True, None) is True
    finally:
        get_settings.cache_clear()


def test_lazy_engine_and_session_factory_fail_clearly_without_database_url() -> None:
    settings = Settings(_env_file=None, APP_ENV="test", DATABASE_URL=None)

    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        get_engine(settings)

    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        get_session_factory(settings)


def test_session_sqlite_enables_foreign_keys_and_postgres_pooler_disables_prepared_statements(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fk_pragma.db"
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{db_path.as_posix()}",
    )
    try:
        engine = get_engine(settings)
        with engine.connect() as conn:
            fk_enabled = conn.execute(text("PRAGMA foreign_keys")).scalar_one()
        assert fk_enabled == 1
    finally:
        dispose_engine()

    pooler_url = normalize_postgres_url(
        "postgresql://user:pass@ep-cool-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
    )
    direct_url = normalize_postgres_url(
        "postgresql://user:pass@ep-cool.us-east-1.aws.neon.tech/neondb?sslmode=require"
    )
    assert _postgres_connect_args(pooler_url) == {
        "connect_timeout": 10,
        "prepare_threshold": None,
    }
    assert _postgres_connect_args(direct_url) == {"connect_timeout": 10}


def test_sqlite_foreign_keys_cascade_and_check_constraints_enforced(tmp_path: Path) -> None:
    with _isolated_sqlite_session_factory(tmp_path / "integrity.db") as (_engine, factory):
        with factory() as db:
            # FK enforcement: missing created_by user must fail
            orphan_exam = Exam(
                id=uuid4(),
                title="Orphan",
                duration_minutes=30,
                created_by=uuid4(),
            )
            db.add(orphan_exam)
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()

            # CheckConstraint enforcement on ApplicationUser.role
            bad_user = ApplicationUser(
                id=uuid4(),
                auth_subject="bad-role-sub",
                role="SUPERUSER",
            )
            db.add(bad_user)
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()

            _admin, student, exam, question = _seed_admin_and_exam(db)
            opt_a = QuestionOption(
                id=uuid4(),
                question_id=question.id,
                label="A",
                option_text="Mitochondria",
                is_correct=True,
                position=0,
            )
            opt_b = QuestionOption(
                id=uuid4(),
                question_id=question.id,
                label="B",
                option_text="Nucleus",
                is_correct=False,
                position=1,
            )
            db.add_all([opt_a, opt_b])
            db.flush()

            now = datetime.now(UTC)
            attempt = ExamAttempt(
                id=uuid4(),
                exam_id=exam.id,
                user_id=student.id,
                started_at=now,
                expires_at=now + timedelta(minutes=45),
                status="IN_PROGRESS",
                total_questions=1,
            )
            db.add(attempt)
            db.flush()

            db.add(
                AttemptQuestion(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    display_order=0,
                )
            )
            answer = StudentAnswer(
                id=uuid4(),
                attempt_id=attempt.id,
                question_id=question.id,
                selected_option_id=opt_a.id,
            )
            db.add(answer)
            db.commit()

            # Deleting selected option sets selected_option_id to NULL (ON DELETE SET NULL)
            db.delete(opt_a)
            db.commit()
            db.expire_all()
            refreshed_answer = db.get(StudentAnswer, answer.id)
            assert refreshed_answer is not None
            assert refreshed_answer.selected_option_id is None

            # Deleting exam cascades across questions, options, attempts, links, and answers
            db.delete(exam)
            db.commit()
            assert db.get(Question, question.id) is None
            assert db.get(QuestionOption, opt_b.id) is None
            assert db.get(ExamAttempt, attempt.id) is None
            assert db.get(StudentAnswer, answer.id) is None


def test_partial_unique_indexes_and_attempt_question_order_uniqueness(
    tmp_path: Path,
) -> None:
    with _isolated_sqlite_session_factory(tmp_path / "partial_indexes.db") as (_engine, factory):
        with factory() as db:
            _admin, student, exam, question = _seed_admin_and_exam(db)
            second_student = ApplicationUser(
                id=uuid4(),
                auth_subject="sub-student-2",
                email="student2@example.edu",
                role=ROLE_STUDENT,
            )
            second_question = Question(
                id=uuid4(),
                exam_id=exam.id,
                question_text="Second question?",
                position=2,
            )
            db.add_all([second_student, second_question])
            db.flush()

            # Multiple is_correct=False options + 1 is_correct=True option allowed
            db.add_all(
                [
                    QuestionOption(
                        id=uuid4(),
                        question_id=question.id,
                        label="A",
                        option_text="Wrong 1",
                        is_correct=False,
                        position=0,
                    ),
                    QuestionOption(
                        id=uuid4(),
                        question_id=question.id,
                        label="B",
                        option_text="Wrong 2",
                        is_correct=False,
                        position=1,
                    ),
                    QuestionOption(
                        id=uuid4(),
                        question_id=question.id,
                        label="C",
                        option_text="Correct",
                        is_correct=True,
                        position=2,
                    ),
                ]
            )
            db.commit()

            # Second is_correct=True option on same question violates partial unique index
            db.add(
                QuestionOption(
                    id=uuid4(),
                    question_id=question.id,
                    label="D",
                    option_text="Duplicate Correct",
                    is_correct=True,
                    position=3,
                )
            )
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()

            # Multiple GRADED attempts + 1 IN_PROGRESS attempt allowed for same (user_id, exam_id)
            now = datetime.now(UTC)
            graded_attempt = ExamAttempt(
                id=uuid4(),
                exam_id=exam.id,
                user_id=student.id,
                started_at=now - timedelta(hours=2),
                expires_at=now - timedelta(hours=1),
                submitted_at=now - timedelta(hours=1, minutes=10),
                status="GRADED",
                submission_reason="STUDENT_SUBMITTED",
                total_questions=2,
            )
            active_attempt = ExamAttempt(
                id=uuid4(),
                exam_id=exam.id,
                user_id=student.id,
                started_at=now,
                expires_at=now + timedelta(minutes=45),
                status="IN_PROGRESS",
                total_questions=2,
            )
            other_student_active = ExamAttempt(
                id=uuid4(),
                exam_id=exam.id,
                user_id=second_student.id,
                started_at=now,
                expires_at=now + timedelta(minutes=45),
                status="IN_PROGRESS",
                total_questions=2,
            )
            db.add_all([graded_attempt, active_attempt, other_student_active])
            db.commit()

            # Second IN_PROGRESS attempt for same (user_id, exam_id) violates partial unique index
            db.add(
                ExamAttempt(
                    id=uuid4(),
                    exam_id=exam.id,
                    user_id=student.id,
                    started_at=now,
                    expires_at=now + timedelta(minutes=45),
                    status="IN_PROGRESS",
                    total_questions=2,
                )
            )
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()

            # Duplicate display_order within same attempt violates unique index
            db.add(
                AttemptQuestion(
                    attempt_id=active_attempt.id,
                    question_id=question.id,
                    display_order=0,
                )
            )
            db.commit()
            db.add(
                AttemptQuestion(
                    attempt_id=active_attempt.id,
                    question_id=second_question.id,
                    display_order=0,
                )
            )
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()


def test_alembic_infrastructure_has_single_linear_head_0006() -> None:
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))

    assert not alembic_cfg.get_main_option("sqlalchemy.url")

    script_dir = ScriptDirectory.from_config(alembic_cfg)
    assert script_dir.get_heads() == ["0006_submission_reason"]

    history_revs = [rev.revision for rev in script_dir.walk_revisions()]
    assert history_revs == [
        "0006_submission_reason",
        "0005_exam_pdf_sources",
        "0004_exam_closed_at_and_indexes",
        "0003_attempt_option_order",
        "0002_examination_schema",
        "0001_application_users",
    ]

    versions_dir = backend_dir / "alembic" / "versions"
    migration_py_files = sorted(p.name for p in versions_dir.glob("*.py"))
    assert migration_py_files == [
        "0001_application_users.py",
        "0002_examination_schema.py",
        "0003_attempt_option_order.py",
        "0004_exam_closed_at_and_indexes.py",
        "0005_exam_pdf_sources.py",
        "0006_submission_reason.py",
    ]


def test_alembic_full_chain_offline_postgres_upgrade_and_downgrade_sql(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://placeholder:placeholder@ep-direct.us-east-1.aws.neon.tech/neondb?sslmode=require",
    )
    get_settings.cache_clear()

    try:
        command.upgrade(alembic_cfg, "head", sql=True)
        upgrade_sql = capsys.readouterr().out

        for table_name in (
            "application_users",
            "exams",
            "questions",
            "question_options",
            "exam_attempts",
            "attempt_questions",
            "student_answers",
            "exam_source_files",
        ):
            assert f"CREATE TABLE {table_name} (" in upgrade_sql

        assert "ALTER TABLE attempt_questions ADD COLUMN option_order TEXT;" in upgrade_sql
        assert (
            "ALTER TABLE exam_attempts ALTER COLUMN submission_reason TYPE VARCHAR(32);"
            in upgrade_sql
        )
        assert "ALTER TABLE exams ADD COLUMN closed_at TIMESTAMP WITH TIME ZONE;" in upgrade_sql
        assert "ALTER TABLE student_answers ALTER COLUMN answered_at SET DEFAULT now();" in (
            upgrade_sql
        )
        assert "ALTER TABLE student_answers ALTER COLUMN updated_at SET DEFAULT now();" in (
            upgrade_sql
        )
        assert "CREATE INDEX ix_exams_status ON exams (status);" in upgrade_sql
        assert "CREATE INDEX ix_exams_created_by ON exams (created_by);" in upgrade_sql
        assert "CREATE INDEX ix_questions_exam_id_position ON questions (exam_id, position);" in (
            upgrade_sql
        )
        assert (
            "CREATE INDEX ix_question_options_question_id ON question_options (question_id);"
            in upgrade_sql
        )
        assert (
            "CREATE UNIQUE INDEX uq_question_options_one_correct_per_question "
            "ON question_options (question_id) WHERE is_correct IS TRUE;"
        ) in upgrade_sql
        assert (
            "CREATE INDEX ix_exam_attempts_user_id_exam_id ON exam_attempts (user_id, exam_id);"
            in upgrade_sql
        )
        assert (
            "CREATE INDEX ix_exam_attempts_exam_id_status ON exam_attempts (exam_id, status);"
            in upgrade_sql
        )
        assert (
            "CREATE UNIQUE INDEX uq_exam_attempts_active_user_exam "
            "ON exam_attempts (user_id, exam_id) WHERE status = 'IN_PROGRESS';"
        ) in upgrade_sql
        assert (
            "CREATE UNIQUE INDEX uq_attempt_questions_attempt_id_display_order "
            "ON attempt_questions (attempt_id, display_order);"
        ) in upgrade_sql
        assert (
            "CREATE INDEX ix_student_answers_attempt_id ON student_answers (attempt_id);"
            in upgrade_sql
        )

        command.downgrade(
            alembic_cfg,
            "0004_exam_closed_at_and_indexes:0003_attempt_option_order",
            sql=True,
        )
        downgrade_sql = capsys.readouterr().out

        assert "DROP INDEX ix_student_answers_attempt_id;" in downgrade_sql
        assert "DROP INDEX uq_attempt_questions_attempt_id_display_order;" in downgrade_sql
        assert "DROP INDEX uq_exam_attempts_active_user_exam;" in downgrade_sql
        assert "DROP INDEX ix_exam_attempts_exam_id_status;" in downgrade_sql
        assert "DROP INDEX ix_exam_attempts_user_id_exam_id;" in downgrade_sql
        assert "DROP INDEX uq_question_options_one_correct_per_question;" in downgrade_sql
        assert "DROP INDEX ix_question_options_question_id;" in downgrade_sql
        assert "DROP INDEX ix_questions_exam_id_position;" in downgrade_sql
        assert "DROP INDEX ix_exams_created_by;" in downgrade_sql
        assert "DROP INDEX ix_exams_status;" in downgrade_sql
        assert "ALTER TABLE student_answers ALTER COLUMN updated_at DROP DEFAULT;" in downgrade_sql
        assert "ALTER TABLE student_answers ALTER COLUMN answered_at DROP DEFAULT;" in downgrade_sql
        assert "ALTER TABLE exams DROP COLUMN closed_at;" in downgrade_sql
    finally:
        get_settings.cache_clear()
