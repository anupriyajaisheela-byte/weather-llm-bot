import sys

if __name__ == '__main__':
    # Simple manage.py wrapper: python manage.py runserver
    if len(sys.argv) >= 2 and sys.argv[1] in ('runserver', 'run'):
        # run via uvicorn
        import uvicorn
        host = '127.0.0.1'
        port = 8000
        reload = True
        # allow overriding
        for a in sys.argv[2:]:
            if a.startswith('--host='):
                host = a.split('=',1)[1]
            if a.startswith('--port='):
                port = int(a.split('=',1)[1])
            if a == '--no-reload':
                reload = False
        uvicorn.run('app.main:app', host=host, port=port, reload=reload)
    else:
        print('Usage: python manage.py runserver [--host=127.0.0.1] [--port=8000] [--no-reload]')
