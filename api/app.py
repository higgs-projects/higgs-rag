import os

# It seems that JetBrains Python debugger does not work well with gevent,
# so we need to disable gevent in debug mode.
# If you are using debugpy and set GEVENT_SUPPORT=True, you can debug with gevent.
if (flask_debug := os.environ.get("FLASK_DEBUG", "0")) and flask_debug.lower() in {"false", "0", "no"}:
    from gevent import monkey

    # gevent
    monkey.patch_all()

    from grpc.experimental import gevent as grpc_gevent  # type: ignore

    # grpc gevent
    grpc_gevent.init_gevent()

    import psycogreen.gevent  # type: ignore

    psycogreen.gevent.patch_psycopg()

from app_factory import create_app

app = create_app()
celery = app.extensions["celery"]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5011)
