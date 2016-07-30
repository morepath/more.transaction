import morepath

from transaction import TransactionManager
from transaction.interfaces import TransientError
from more.transaction import TransactionApp
from more.transaction.main import (transaction_tween_factory,
                                   default_commit_veto)
from webtest import TestApp as Client
import pytest


def test_multiple_path_variables():

    class TestApp(TransactionApp):
        attempts = 0

    @TestApp.path('/{type}/{id}')
    class Document(object):
        def __init__(self, type, id):
            self.type = type
            self.id = id

    @TestApp.view(model=Document)
    def view_document(self, request):
        TestApp.attempts += 1

        # on the first attempt raise a conflict error
        if TestApp.attempts == 1:
            raise Conflict

        return 'ok'

    @TestApp.setting(section='transaction', name='attempts')
    def get_retry_attempts():
        return 2

    client = Client(TestApp())
    response = client.get('/document/1')
    assert response.text == 'ok'
    assert TestApp.attempts == 2


def test_reset_unconsumed_path():

    class TestApp(TransactionApp):
        attempts = 0

    @TestApp.path('/foo/bar')
    class Foo(object):
        pass

    @TestApp.view(model=Foo)
    def view_foo(self, request):
        TestApp.attempts += 1

        # on the first attempt raise a conflict error
        if TestApp.attempts == 1:
            raise Conflict

        return 'ok'

    # if the unconsumed path is reset wrongly, it'll accidentally pick
    # up this model instead of Foo
    @TestApp.path('/bar/foo')
    class Bar(object):
        pass

    @TestApp.view(model=Bar)
    def view_bar(self, request):
        return 'error'

    @TestApp.setting(section='transaction', name='attempts')
    def get_retry_attempts():
        return 2

    client = Client(TestApp())
    response = client.get('/foo/bar')
    assert response.text == 'ok'
    assert TestApp.attempts == 2


def test_reset_app():
    class RootApp(TransactionApp):
        attempts = 0

    class TestApp(morepath.App):
        pass

    @RootApp.mount(app=TestApp, path='/mount')
    def mount_testapp():
        return TestApp()

    @TestApp.path('/sub')
    class Foo(object):
        pass

    @TestApp.view(model=Foo)
    def view_foo(self, request):
        RootApp.attempts += 1

        # on the first attempt raise a conflict error
        if RootApp.attempts == 1:
            raise Conflict

        return 'ok'

    @RootApp.setting(section='transaction', name='attempts')
    def get_retry_attempts():
        return 2

    client = Client(RootApp())
    response = client.get('/mount/sub')
    assert response.text == 'ok'
    assert RootApp.attempts == 2


def test_handler_exception():

    def handler(request):
        raise NotImplementedError

    txn = DummyTransaction()
    publish = transaction_tween_factory(DummyApp(), handler, txn)

    with pytest.raises(NotImplementedError):
        publish(DummyRequest())

    assert txn.began
    assert txn.aborted
    assert not txn.committed


def test_handler_retryable_exception():
    from transaction.interfaces import TransientError

    class Conflict(TransientError):
        pass

    count = []
    response = DummyResponse()
    app = DummyApp()
    app.settings.transaction.attempts = 3

    def handler(request, count=count):
        count.append(True)
        if len(count) == 3:
            return response
        raise Conflict

    txn = DummyTransaction(retryable=True)

    publish = transaction_tween_factory(app, handler, txn)

    request = DummyRequest()

    result = publish(request)

    assert txn.began
    assert txn.committed == 1
    assert txn.aborted == 2
    assert request.made_seekable == 3
    assert result is response


def test_handler_retryable_exception_defaults_to_1():
    count = []

    def handler(request, count=count):
        raise Conflict

    publish = transaction_tween_factory(DummyApp(),
                                        handler, DummyTransaction())

    with pytest.raises(Conflict):
        publish(DummyRequest())


def test_handler_isdoomed():
    txn = DummyTransaction(doomed=True)

    def handler(request):
        return

    publish = transaction_tween_factory(DummyApp(), handler, txn)

    publish(DummyRequest())

    assert txn.began
    assert txn.aborted
    assert not txn.committed


def test_handler_notes():
    txn = DummyTransaction()

    def handler(request):
        return DummyResponse()

    publish = transaction_tween_factory(DummyApp(), handler, txn)

    publish(DummyRequest())
    assert txn._note == '/'
    assert txn.username is None


def test_identity():
    txn = DummyTransaction()
    request = DummyRequest()
    request.identity = morepath.Identity('foo')

    def handler(request):
        return DummyResponse()

    publish = transaction_tween_factory(DummyApp(), handler, txn)

    publish(request)
    assert txn.username == ':foo'


def test_500_without_commit_veto():
    response = DummyResponse()
    response.status = '500 Bad Request'

    def handler(request):
        return response

    txn = DummyTransaction()
    publish = transaction_tween_factory(DummyApp(), handler, txn)
    result = publish(DummyRequest())
    assert result is response
    assert txn.began
    assert not txn.aborted
    assert txn.committed


def test_500_with_default_commit_veto():
    app = DummyApp()
    app.settings.transaction.commit_veto = default_commit_veto

    response = DummyResponse()
    response.status = '500 Bad Request'

    def handler(request):
        return response

    txn = DummyTransaction()
    publish = transaction_tween_factory(app, handler, txn)
    result = publish(DummyRequest())
    assert result is response
    assert txn.began
    assert txn.aborted
    assert not txn.committed


def test_null_commit_veto():
    response = DummyResponse()
    response.status = '500 Bad Request'

    def handler(request):
        return response

    app = DummyApp()
    app.settings.transaction.commit_veto = None

    txn = DummyTransaction()
    publish = transaction_tween_factory(app, handler, txn)
    result = publish(DummyRequest())

    assert result is response
    assert txn.began
    assert not txn.aborted
    assert txn.committed


def test_commit_veto_true():
    app = DummyApp()

    def veto_true(request, response):
        return True

    app.settings.transaction.commit_veto = veto_true

    response = DummyResponse()

    def handler(request):
        return response

    txn = DummyTransaction()
    publish = transaction_tween_factory(app, handler, txn)
    result = publish(DummyRequest())

    assert result is response
    assert txn.began
    assert txn.aborted
    assert not txn.committed


def test_commit_veto_false():
    app = DummyApp()

    def veto_false(request, response):
        return False

    app.settings.transaction.commit_veto = veto_false

    response = DummyResponse()

    def handler(request):
        return response

    txn = DummyTransaction()
    publish = transaction_tween_factory(app, handler, txn)
    result = publish(DummyRequest())

    assert result is response
    assert txn.began
    assert not txn.aborted
    assert txn.committed


def test_commitonly():
    response = DummyResponse()

    def handler(request):
        return response

    txn = DummyTransaction()
    publish = transaction_tween_factory(DummyApp(), handler, txn)
    result = publish(DummyRequest())

    assert result is response
    assert txn.began
    assert not txn.aborted
    assert txn.committed


class DummySettingsSectionContainer(object):
    def __init__(self):
        self.transaction = DummyTransactionSettingSection()


class DummyTransactionSettingSection(object):
    def __init__(self):
        self.attempts = 1
        self.commit_veto = None


class DummyApp(object):
    def __init__(self):
        self.settings = DummySettingsSectionContainer()


class DummyTransaction(TransactionManager):
    began = False
    committed = False
    aborted = False
    _resources = []
    username = None

    def __init__(self, doomed=False, retryable=False):
        self.doomed = doomed
        self.began = 0
        self.committed = 0
        self.aborted = 0
        self.retryable = retryable
        self.active = False

    @property
    def manager(self):
        return self

    def _retryable(self, t, v):
        if self.active:
            return self.retryable

    def get(self):
        return self

    def setUser(self, name, path='/'):
        self.username = "%s:%s" % (path, name)

    def isDoomed(self):
        return self.doomed

    def begin(self):
        self.began += 1
        self.active = True
        return self

    def commit(self):
        self.committed += 1

    def abort(self):
        self.active = False
        self.aborted += 1

    def note(self, value):
        self._note = value


class DummyRequest(object):
    path = '/'
    identity = morepath.NO_IDENTITY

    def __init__(self):
        self.environ = {}
        self.made_seekable = 0

    def make_body_seekable(self):
        self.made_seekable += 1

    def reset(self):
        self.make_body_seekable()

    @property
    def path_info(self):
        return self.path


class DummyResponse(object):
    def __init__(self, status='200 OK', headers=None):
        self.status = status
        if headers is None:
            headers = {}
        self.headers = headers


class Conflict(TransientError):
        pass
