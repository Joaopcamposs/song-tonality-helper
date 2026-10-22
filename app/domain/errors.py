"""Erros de regra do domínio e dos serviços; os routers os traduzem para HTTP."""


class DomainError(Exception):
    """Erro de regra com mensagem legível para o usuário."""

    def __init__(self, message: str) -> None:
        """Guarda a mensagem mostrada no relatório de erro."""
        super().__init__(message)
        self.message = message


class NoMelodyError(DomainError):
    """O áudio não tem nenhuma nota sustentada o bastante para ser a melodia."""


class InvalidUrlError(DomainError):
    """O link não é um endereço aceito do YouTube."""


class VideoTooLongError(DomainError):
    """O vídeo passa da duração máxima aceita."""


class DownloadError(DomainError):
    """Falha ao baixar ou converter o áudio."""
