from .app import create_app
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--foreground", action="store_true")
    args = parser.parse_args()

    app, socketio = create_app(args.filename, args.port)

    if args.foreground:
        socketio.run(app, host="0.0.0.0", port=args.port)
    else:
        socketio.run(app, port=args.port)

if __name__ == "__main__":
    main()

