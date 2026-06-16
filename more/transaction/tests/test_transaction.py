from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import morepath

from transaction import TransactionManager
from transaction.interfaces import TransientError
from more.transaction import TransactionApp
from more.transaction.main import transaction_tween_factory, default_commit_veto
from webtest import TestApp as Client


def test_multiple_path_variables() -> None:
    class TestApp(TransactionApp):
        attempts = 0

    @TestApp.path("/{type}/{id}")
    class Document:
        def __init__(self, type: str, id: str) -> None:
            self.type = type
            self.id = id

    @TestApp.view(model=Document)
    def view_document(self: Document, request: morepath.Request) -> str:
        TestApp.attempts += 1

        # on the first attempt raise a conflict error
        if TestApp.attempts == 1:
            raise Conflict

        return "ok"

    @TestApp.setting(section="transaction", name="attempts")
    def get_retry_attempts() -> int:
        return 2

    client = Client(TestApp())
    response = client.get("/document/1")
    assert response.text == "ok"
    assert TestApp.attempts == 2


def test_reset_unconsumed_path() -> None:
    class TestApp(TransactionApp):
        attempts = 0

    @TestApp.path("/foo/bar")
    class Foo:
        pass

    @TestApp.view(model=Foo)
    def view_foo(self: Foo, request: morepath.Request) -> str:
        TestApp.attempts += 1

        # on the first attempt raise a conflict error
        if TestApp.attempts == 1:
            raise Conflict

        return "ok"

    # if the unconsumed path is reset wrongly, it'll accidentally pick
    # up this model instead of Foo
    @TestApp.path("/bar/foo")
    class Bar:
        pass

    @TestApp.view(model=Bar)
    def view_bar(self: Bar, request: morepath.Request) -> str:
        return "error"

    @TestApp.setting(section="transaction", name="attempts")
    def get_retry_attempts() -> int:
        return 2

    client = Client(TestApp())
    response = client.get("/foo/bar")
    assert response.text == "ok"
    assert TestApp.attempts == 2


def test_reset_app() -> None:
    class RootApp(TransactionApp):
        attempts = 0

    class TestApp(morepath.App):
        pass

    @RootApp.mount(app=TestApp, path="/mount")
    def mount_testapp() -> TestApp:
        return TestApp()

    @TestApp.path("/sub")
    class Foo:
        pass

    @TestApp.view(model=Foo)
    def view_foo(self: Foo, request: morepath.Request) -> str:
        RootApp.attempts += 1

        # on the first attempt raise a conflict error
        if RootApp.attempts == 1:
            raise Conflict

        return "ok"

    @RootApp.setting(section="transaction", name="attempts")
    def get_retry_attempts() -> int:
        return 2

    client = Client(RootApp())
    response = client.get("/mount/sub")
    assert response.text == "ok"
    assert RootApp.attempts == 2


def test_handler_exception() -> None:
    def handler(request: morepath.Request) -> morepath.Response:
        raise NotImplementedError

    txn = DummyTransaction()
    publish: Any = transaction_tween_factory(DummyApp(), handler, txn)

    with pytest.raises(NotImplementedError):
        publish(DummyRequest())

    assert txn.began
    assert txn.aborted
    assert not txn.committed


def test_handler_retryable_exception() -> None:
    from transaction.interfaces import TransientError

    class Conflict(TransientError):  # type: ignore[misc]
        pass

    count: list[bool] = []
    response = DummyResponse()
    app = DummyApp()
    app.settings.transaction.attempts = 3

    def handler(request: morepath.Request, count: list[bool] = count) -> Any:
        count.append(True)
        if len(count) == 3:
            return response
        raise Conflict

    txn = DummyTransaction(retryable=True)

    publish: Any = transaction_tween_factory(app, handler, txn)

    request = DummyRequest()

    result = publish(request)

    assert txn.began
    assert txn.committed == 1
    assert txn.aborted == 2
    assert request.made_seekable == 3
    assert result is response


def test_handler_retryable_exception_defaults_to_1() -> None:

    def handler(request: morepath.Request) -> Any:
        raise Conflict

    publish: Any = transaction_tween_factory(DummyApp(), handler, DummyTransaction())

    with pytest.raises(Conflict):
        publish(DummyRequest())


def test_handler_isdoomed() -> None:
    txn = DummyTransaction(doomed=True)

    def handler(request: morepath.Request) -> Any:
        return

    publish: Any = transaction_tween_factory(DummyApp(), handler, txn)

    publish(DummyRequest())

    assert txn.began
    assert txn.aborted
    assert not txn.committed


def test_handler_notes() -> None:
    txn = DummyTransaction()

    def handler(request: morepath.Request) -> Any:
        return DummyResponse()

    publish: Any = transaction_tween_factory(DummyApp(), handler, txn)

    publish(DummyRequest())
    assert txn._note == "/"
    assert txn.username is None


def test_identity() -> None:
    txn = DummyTransaction()
    request = DummyRequest()
    request.identity = morepath.Identity("foo")

    def handler(request: morepath.Request) -> Any:
        return DummyResponse()

    publish: Any = transaction_tween_factory(DummyApp(), handler, txn)

    publish(request)
    assert txn.username == ":foo"


def test_500_without_commit_veto() -> None:
    response = DummyResponse()
    response.status = "500 Bad Request"

    def handler(request: morepath.Request) -> Any:
        return response

    txn = DummyTransaction()
    publish: Any = transaction_tween_factory(DummyApp(), handler, txn)
    result = publish(DummyRequest())
    assert result is response
    assert txn.began
    assert not txn.aborted
    assert txn.committed


def test_500_with_default_commit_veto() -> None:
    app = DummyApp()
    app.settings.transaction.commit_veto = default_commit_veto

    response = DummyResponse()
    response.status = "500 Bad Request"

    def handler(request: morepath.Request) -> Any:
        return response

    txn = DummyTransaction()
    publish: Any = transaction_tween_factory(app, handler, txn)
    result = publish(DummyRequest())
    assert result is response
    assert txn.began
    assert txn.aborted
    assert not txn.committed


def test_null_commit_veto() -> None:
    response = DummyResponse()
    response.status = "500 Bad Request"

    def handler(request: morepath.Request) -> Any:
        return response

    app = DummyApp()
    app.settings.transaction.commit_veto = None

    txn = DummyTransaction()
    publish: Any = transaction_tween_factory(app, handler, txn)
    result = publish(DummyRequest())

    assert result is response
    assert txn.began
    assert not txn.aborted
    assert txn.committed


def test_commit_veto_true() -> None:
    app = DummyApp()

    def veto_true(request: object, response: object) -> bool:
        return True

    app.settings.transaction.commit_veto = veto_true

    response = DummyResponse()

    def handler(request: morepath.Request) -> Any:
        return response

    txn = DummyTransaction()
    publish: Any = transaction_tween_factory(app, handler, txn)
    result = publish(DummyRequest())

    assert result is response
    assert txn.began
    assert txn.aborted
    assert not txn.committed


def test_commit_veto_false() -> None:
    app = DummyApp()

    def veto_false(request: object, response: object) -> bool:
        return False

    app.settings.transaction.commit_veto = veto_false

    response = DummyResponse()

    def handler(request: morepath.Request) -> Any:
        return response

    txn = DummyTransaction()
    publish: Any = transaction_tween_factory(app, handler, txn)
    result = publish(DummyRequest())

    assert result is response
    assert txn.began
    assert not txn.aborted
    assert txn.committed


def test_commitonly() -> None:
    response = DummyResponse()

    def handler(request: morepath.Request) -> Any:
        return response

    txn = DummyTransaction()
    publish: Any = transaction_tween_factory(DummyApp(), handler, txn)
    result = publish(DummyRequest())

    assert result is response
    assert txn.began
    assert not txn.aborted
    assert txn.committed


if TYPE_CHECKING:
    from more.transaction import TransactionApp as DummyApp
else:

    class DummySettingsSectionContainer:
        def __init__(self) -> None:
            self.transaction = DummyTransactionSettingSection()

    class DummyTransactionSettingSection:
        def __init__(self) -> None:
            self.attempts = 1
            self.commit_veto = None

    class DummyApp:
        def __init__(self) -> None:
            self.settings = DummySettingsSectionContainer()


class DummyTransaction(TransactionManager):  # type: ignore[misc]
    _resources: list[Any] = []
    username: str | None = None

    def __init__(self, doomed: bool = False, retryable: bool = False) -> None:
        self.doomed = doomed
        self.began = 0
        self.committed = 0
        self.aborted = 0
        self.retryable = retryable
        self.active = False

    @property
    def manager(self) -> DummyTransaction:
        return self

    def _retryable(self, t: object, v: object) -> bool:  # pyright: ignore
        if self.active:
            return self.retryable
        return False

    def get(self) -> DummyTransaction:  # pyright: ignore
        return self

    def setUser(self, name: str, path: str = "/") -> None:
        self.username = f"{path}:{name}"

    def isDoomed(self) -> bool:
        return self.doomed

    def begin(self) -> DummyTransaction:  # pyright: ignore
        self.began += 1
        self.active = True
        return self

    def commit(self) -> None:
        self.committed += 1

    def abort(self) -> None:
        self.active = False
        self.aborted += 1

    def note(self, value: Any) -> None:
        self._note = value


class DummyRequest:
    path = "/"
    identity: Any = morepath.NO_IDENTITY

    def __init__(self) -> None:
        self.environ: dict[str, Any] = {}
        self.made_seekable = 0

    def make_body_seekable(self) -> None:
        self.made_seekable += 1

    def reset(self) -> None:
        self.make_body_seekable()

    @property
    def path_info(self) -> str:
        return self.path


class DummyResponse:
    def __init__(
        self, status: str = "200 OK", headers: dict[str, str] | None = None
    ) -> None:
        self.status = status
        if headers is None:
            headers = {}
        self.headers = headers


class Conflict(TransientError):  # type: ignore[misc]
    pass
