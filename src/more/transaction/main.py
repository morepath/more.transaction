from __future__ import annotations

import sys
import morepath
import transaction

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from morepath.request import Request
    from morepath.types import Tween
    from webob import Response as BaseResponse


class TransactionApp(morepath.App):
    pass


# code taken and adjusted from pyramid_tm


def default_commit_veto(request: object, response: BaseResponse) -> bool:
    """
    When used as a commit veto, the logic in this function will cause the
    transaction to be aborted if:

    - An ``X-Tm`` response header with the value ``abort`` (or any value
      other than ``commit``) exists.

    - The response status code starts with ``4`` or ``5``.

    Otherwise the transaction will be allowed to commit.
    """
    xtm = response.headers.get("x-tm")
    if xtm is not None:
        return xtm != "commit"
    return response.status.startswith(("4", "5"))


class AbortResponse(Exception):
    def __init__(self, response: BaseResponse) -> None:
        self.response = response


@TransactionApp.setting_section(section="transaction")
def get_transaction_settings() -> dict[str, Any]:
    return {"attempts": 1, "commit_veto": default_commit_veto}


@TransactionApp.tween_factory(over=morepath.EXCVIEW)
def transaction_tween_factory(
    app: TransactionApp, handler: Tween, transaction: Any = transaction
) -> Tween:
    attempts = app.settings.transaction.attempts
    commit_veto = app.settings.transaction.commit_veto

    def transaction_tween(request: Request) -> BaseResponse:
        manager = transaction.manager
        number = attempts
        userid = request.identity.userid

        while number:
            number -= 1
            try:
                manager.begin()
                # make_body_seekable will copy wsgi.input if necessary,
                # otherwise it will rewind the copy to position zero
                if attempts != 1:
                    request.reset()
                t = manager.get()
                if userid is not None:
                    t.setUser(userid, "")
                t.note(str(request.path))
                response = handler(request)
                if manager.isDoomed():
                    raise AbortResponse(response)
                if commit_veto is not None:
                    veto = commit_veto(request, response)
                    if veto:
                        raise AbortResponse(response)
                manager.commit()
                return response
            except AbortResponse as e:
                manager.abort()
                return e.response
            except Exception:
                ex_type, ex_value = sys.exc_info()[:2]
                retryable = manager.manager._retryable(ex_type, ex_value)
                manager.abort()
                if (number <= 0) or (not retryable):
                    raise
        raise AssertionError("unreachable")  # pragma: no cover

    return transaction_tween
