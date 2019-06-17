from webapp import create_app
import logging

app = create_app()

if __name__ == '__main__':
    logging.info("Server starting.")
    # app.run(debug=False)
    app.run(host="0.0.0.0", debug=True)
    logging.info("Server stopped.")
