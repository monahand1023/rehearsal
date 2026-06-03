class TTSError(Exception):
    pass


class TTSProvider:
    def synthesize(self, text: str, language: str = "en") -> bytes:
        raise NotImplementedError
