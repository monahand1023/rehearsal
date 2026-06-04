from engine.constants import LANG_EN


class TTSError(Exception):
    pass


class TTSProvider:
    media_type = "audio/mpeg"   # response content-type for the synthesized audio

    def synthesize(self, text: str, language: str = LANG_EN) -> bytes:
        raise NotImplementedError
