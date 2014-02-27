import sys
import morepath
import transaction
from .compat import reraise

app = morepath.App()

# code taken and adjusted from pyramid_tm

def default_commit_veto(request, response):
    """
    When used as a commit veto, the logic in this function will cause the
    transaction to be aborted if:

    - An ``X-Tm`` response header with the value ``abort`` (or any value
      other than ``commit``) exists.

    - The response status code starts with ``4`` or ``5``.

    Otherwise the transaction will be allowed to commit.
    """
    xtm = response.headers.get('x-tm')
    if xtm is not None:
        return xtm != 'commit'
    return response.status.startswith(('4', '5'))


class AbortResponse(Exception):
    def __init__(self, response):
        self.response = response

@app.tween_factory()
def transaction_tween_factory(app, handler, transaction=transaction):
    # XXX need proper simple config system in morepath
    attempts = int(getattr(app, 'transaction_attempts', 1))
    commit_veto = getattr(app, 'transaction_commit_veto', None)

    def transaction_tween(request, mount):
        manager = transaction.manager
        number = attempts
        userid = None # XXX get from identity on request

        while number:
            number -= 1
            try:
                manager.begin()
                # XXX what is this about?
                # make_body_seekable will copy wsgi.input if necessary,
                # otherwise it will rewind the copy to position zero
                #if attempts != 1:
                #    request.make_body_seekable()
                t = manager.get()
                if userid:
                    t.setUser(userid, '')
                t.note(request.full_path)
                response = handler(request, mount)
                if manager.isDoomed():
                    raise AbortResponse(response)
                if commit_veto is not None:
                    veto = commit_veto(request, response)
                    if veto:
                        raise AbortResponse(response)
                manager.commit()
                return response
            except AbortResponse:
                e = sys.exc_info()[1] # py2.5-py3 compat
                manager.abort()
                return e.response
            except:
                exc_info = sys.exc_info()
                try:
                    retryable = manager._retryable(*exc_info[:-1])
                    manager.abort()
                    if (number <= 0) or (not retryable):
                        reraise(*exc_info)
                finally:
                    del exc_info # avoid leak

    return transaction_tween
