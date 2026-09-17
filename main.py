from service import ClientCommService, ClientCommSimpleService
from tools import CsvSanitizer
from ui import StreamlitApp


def get_client_comm_service() -> ClientCommService:
    return ClientCommSimpleService()


def get_csv_sanitizer() -> CsvSanitizer:
    return CsvSanitizer()

def main():
    app = StreamlitApp(
        client_comm_service=get_client_comm_service(),
        csv_sanitizer=get_csv_sanitizer(),
    )
    app.render_app()


if __name__ == "__main__":
    main()
