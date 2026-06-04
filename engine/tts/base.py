class TTSError(Exception):
    pass


class TTSProvider:
    media_type = "audio/mpeg"   # response content-type for the synthesized audio

    def synthesize(self, text: str, language: str = "en") -> bytes:
        raise NotImplementedError
