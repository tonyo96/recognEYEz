from webapp import create_app
import logging

app = create_app()

if __name__ == '__main__':
    logging.info("Server starting.")
    # app.run(debug=False)

    # Starts flask app on localhost port 5000
    app.run(host="0.0.0.0", debug=True)
    # TODO: Should it be able to read port number from a config file and start like this?
    #  app.run(host="0.0.0.0", debug=True, port=config.port) or something
    logging.info("Server stopped.")
