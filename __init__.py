"""Microsoft TTS multi-voice integration."""
import logging

import voluptuous as vol
from pycsspeechtts import pycsspeechtts
from requests.exceptions import HTTPError

from homeassistant.components.tts import CONF_LANG, Provider, TtsAudioType
from homeassistant.components.tts import generate_media_source_id
from homeassistant.components.tts.const import DATA_TTS_MANAGER
from homeassistant.const import ATTR_ENTITY_ID, CONF_API_KEY, CONF_REGION, CONF_TYPE, PERCENTAGE
from homeassistant.generated.microsoft_tts import SUPPORTED_LANGUAGES
import homeassistant.helpers.config_validation as cv

DOMAIN = "microsoft"
_LOGGER = logging.getLogger(__name__)

CONF_GENDER = "gender"
CONF_OUTPUT = "output"
CONF_RATE = "rate"
CONF_VOLUME = "volume"
CONF_PITCH = "pitch"
CONF_CONTOUR = "contour"
CONF_SERVICE_NAME = "service_name"

GENDERS = ["Female", "Male"]

DEFAULT_LANG = "en-us"
DEFAULT_GENDER = "Female"
DEFAULT_TYPE = "JennyNeural"
DEFAULT_OUTPUT = "audio-24khz-96kbitrate-mono-mp3"
DEFAULT_RATE = 0
DEFAULT_VOLUME = 0
DEFAULT_PITCH = "default"
DEFAULT_CONTOUR = ""
DEFAULT_REGION = "eastus"

VOICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SERVICE_NAME): cv.string,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORTED_LANGUAGES),
        vol.Optional(CONF_GENDER, default=DEFAULT_GENDER): vol.In(GENDERS),
        vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): cv.string,
        vol.Optional(CONF_RATE, default=DEFAULT_RATE): vol.All(
            vol.Coerce(int), vol.Range(-100, 100)
        ),
        vol.Optional(CONF_VOLUME, default=DEFAULT_VOLUME): vol.All(
            vol.Coerce(int), vol.Range(-100, 100)
        ),
        vol.Optional(CONF_PITCH, default=DEFAULT_PITCH): cv.string,
        vol.Optional(CONF_CONTOUR, default=DEFAULT_CONTOUR): cv.string,
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [VOICE_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up all configured Microsoft TTS voices."""
    if DOMAIN not in config:
        return True

    manager = hass.data.get(DATA_TTS_MANAGER)
    if manager is None:
        _LOGGER.error(
            "TTS manager not available — ensure 'tts:' is present in configuration.yaml"
        )
        return False

    for voice_config in config[DOMAIN]:
        service_name = voice_config[CONF_SERVICE_NAME]

        provider = await hass.async_add_executor_job(_create_provider, voice_config)

        # Register provider under its unique service_name as the engine_id
        manager.async_register_legacy_engine(service_name, provider, voice_config)

        # Register the _say service with engine_id bound in the closure
        _register_say_service(hass, service_name)

        _LOGGER.info("Registered Microsoft TTS voice: %s", service_name)

    return True


def _create_provider(voice_config):
    """Create a MicrosoftProvider from a voice config entry."""
    return MicrosoftProvider(
        voice_config[CONF_API_KEY],
        voice_config[CONF_LANG],
        voice_config[CONF_GENDER],
        voice_config[CONF_TYPE],
        voice_config[CONF_RATE],
        voice_config[CONF_VOLUME],
        voice_config[CONF_PITCH],
        voice_config[CONF_CONTOUR],
        voice_config[CONF_REGION],
        voice_config[CONF_SERVICE_NAME],
    )


def _register_say_service(hass, engine_id):
    """Register tts.{engine_id}_say with engine_id bound in closure."""
    schema = vol.Schema(
        {
            vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Required("message"): cv.string,
            vol.Optional("cache"): cv.boolean,
            vol.Optional("language"): cv.string,
            vol.Optional("options"): dict,
        }
    )

    async def async_say_handle(service):
        entity_ids = service.data[ATTR_ENTITY_ID]
        message = service.data["message"]
        cache = service.data.get("cache")
        language = service.data.get("language")
        options = service.data.get("options")

        # engine_id is captured per-voice in this closure
        media_id = generate_media_source_id(
            hass,
            message,
            engine=engine_id,
            language=language,
            options=options,
            cache=cache,
        )

        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: entity_ids,
                "media_content_id": media_id,
                "media_content_type": "music",
            },
            blocking=True,
        )

    hass.services.async_register(
        "tts", f"{engine_id}_say", async_say_handle, schema=schema
    )


class MicrosoftProvider(Provider):
    """The Microsoft Speech API provider."""

    def __init__(
        self,
        apikey,
        lang,
        gender,
        ttype,
        rate,
        volume,
        pitch,
        contour,
        region,
        service_name,
    ):
        """Init Microsoft TTS service."""
        self._apikey = apikey
        self._lang = lang
        self._gender = gender
        self._type = ttype
        self._output = DEFAULT_OUTPUT
        self._rate = f"{rate}{PERCENTAGE}"
        self._volume = f"{volume}{PERCENTAGE}"
        self._pitch = pitch
        self._contour = contour
        self._region = region
        self.name = service_name

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return list(SUPPORTED_LANGUAGES)

    @property
    def supported_options(self):
        """Return list of supported options."""
        return [CONF_GENDER, CONF_TYPE]

    @property
    def default_options(self):
        """Return dict of default options."""
        return {CONF_GENDER: self._gender, CONF_TYPE: self._type}

    def get_tts_audio(self, message, language, options) -> TtsAudioType:
        """Load TTS from Microsoft Speech service."""
        if language is None:
            language = self._lang
        try:
            trans = pycsspeechtts.TTSTranslator(self._apikey, self._region)
            data = trans.speak(
                language=language,
                gender=options[CONF_GENDER],
                voiceType=options[CONF_TYPE],
                output=self._output,
                rate=self._rate,
                volume=self._volume,
                pitch=self._pitch,
                contour=self._contour,
                text=message,
            )
        except HTTPError as ex:
            _LOGGER.error("Error occurred for Microsoft TTS: %s", ex)
            return (None, None)
        return ("mp3", data)
