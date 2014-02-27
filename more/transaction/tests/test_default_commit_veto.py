from more.transaction import default_commit_veto


def callFUT(response, request=None):
    return default_commit_veto(request, response)


def test_it_true_500():
    response = DummyResponse('500 Server Error')
    assert callFUT(response)


def test_it_true_503():
    response = DummyResponse('503 Service Unavailable')
    assert callFUT(response)


def test_it_true_400():
    response = DummyResponse('400 Bad Request')
    assert callFUT(response)


def test_it_true_411():
    response = DummyResponse('411 Length Required')
    assert callFUT(response)


def test_it_false_200():
    response = DummyResponse('200 OK')
    assert not callFUT(response)


def test_it_false_201():
    response = DummyResponse('201 Created')
    assert not callFUT(response)


def test_it_false_301():
    response = DummyResponse('301 Moved Permanently')
    assert not callFUT(response)


def test_it_false_302():
    response = DummyResponse('302 Found')
    assert not callFUT(response)


def test_it_false_x_tm_commit():
    response = DummyResponse('200 OK', {'x-tm': 'commit'})
    assert not callFUT(response)


def test_it_true_x_tm_abort():
    response = DummyResponse('200 OK', {'x-tm': 'abort'})
    assert callFUT(response)


def test_it_true_x_tm_anythingelse():
    response = DummyResponse('200 OK', {'x-tm': ''})
    assert callFUT(response)


class DummyRequest(object):
    path_info = '/'

    def __init__(self):
        self.environ = {}
        self.made_seekable = 0

    def make_body_seekable(self):
        self.made_seekable += 1


class DummyResponse(object):
    def __init__(self, status='200 OK', headers=None):
        self.status = status
        if headers is None:
            headers = {}
        self.headers = headers
