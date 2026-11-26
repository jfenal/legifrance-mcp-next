"""Structured logger utility for the Legifrance MCP server.

Everything here logs to stderr, never stdout: under the stdio transport,
stdout is the JSON-RPC protocol channel, and any stray log line written
there corrupts it for the calling client. An optional file handler can
be added on top for persisting logs past the lifetime of the MCP
client's process. See
https://github.com/jfenal/legifrance-mcp/issues/16.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import structlog

# HTTP clients
HTTP_CLIENT_LOGGERS = {
    "urllib3",
    "urllib3.connectionpool",
    "urllib3.util",
    "urllib3.util.retry",
    "requests",
    "httpx",
}

# AWS SDK
AWS_LOGGERS = {
    "botocore",
    "botocore.client",
    "botocore.credentials",
    "botocore.httpsession",
    "boto3",
    "boto3.resources",
}

# MCP (custom platform)
MCP_LOGGERS = {
    "fastmcp",
    "fastmcp.server",
    "fastmcp.server.http",
    "fastmcp.utilities",
    "fastmcp.utilities.logging",
    "fastmcp.client",
    "fastmcp.transports",
}

# ML/AI frameworks
ML_AI_LOGGERS = {
    "sentence_transformers",
    "transformers",
    "transformers.models",
    "transformers.tokenization_utils",
    "transformers.tokenization_utils_base",
    "transformers.configuration_utils",
    "transformers.modeling_utils",
    "huggingface_hub",
    "huggingface_hub.utils",
    "langchain_huggingface",
    "torch",
    "torch.nn",
}

# Observability / telemetry
OBSERVABILITY_LOGGERS = {
    "langfuse",
    "langfuse.client",
    "langfuse.api",
    "langfuse.callback",
}

# --- Aggregated Sets ---

THIRD_PARTY_LOGGERS: Set[str] = (
    HTTP_CLIENT_LOGGERS
    | AWS_LOGGERS
    | MCP_LOGGERS
    | ML_AI_LOGGERS
    | OBSERVABILITY_LOGGERS
)

ERROR_ONLY_LOGGERS: Set[str] = ML_AI_LOGGERS | OBSERVABILITY_LOGGERS

_LOGGING_CONFIGURED = False


# --- Internal helpers ---


def _clear_handlers(logger: logging.Logger) -> None:
    logger.handlers.clear()
    logger.filters.clear()


def _setup_logger(logger_name: str, level: str) -> None:
    logger = logging.getLogger(logger_name)
    _clear_handlers(logger)
    logger.setLevel(logging.ERROR if logger_name in ERROR_ONLY_LOGGERS else level)
    logger.propagate = True


def _configure_third_party_loggers(log_level: str) -> None:
    """Apply structured logging to selected third-party loggers."""
    for name in THIRD_PARTY_LOGGERS:
        _setup_logger(name, log_level)


def _configure_root_handlers(
    log_level: str, log_file: Optional[Union[str, Path]]
) -> None:
    """Attach root logger handlers explicitly, rather than via `logging.basicConfig`.

    `basicConfig()` is a no-op once the root logger already has a handler
    from anywhere else (e.g. a third-party import) -- which is exactly
    what silently defeated the previous `stream=sys.stdout` config here.
    Explicitly clearing and re-attaching handlers makes this deterministic
    regardless of import order.

    The root logger's own level is kept at DEBUG so a file handler can
    capture full detail even when the console handler (which does honor
    `log_level`) is quieter -- each handler filters independently.
    """
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(message)s")

    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setLevel(log_level)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


# --- Public API ---


def force_reconfigure_all_loggers(
    log_level: str = "INFO", *, log_file: Optional[Union[str, Path]] = None
) -> None:
    """Force logger reconfiguration, even if already initialized."""
    global _LOGGING_CONFIGURED
    _LOGGING_CONFIGURED = False
    get_python_logger(log_level, log_file=log_file)


def get_python_logger(
    log_level: str = "INFO", *, log_file: Optional[Union[str, Path]] = None
) -> structlog.BoundLogger:
    """Get a configured structlog logger.

    `log_file`: when given, also writes full-detail (DEBUG+) logs to
    this path, independent of `log_level` (which only governs the
    stderr/console handler). Opt-in, since writing a file is a side
    effect not every caller wants.
    """
    global _LOGGING_CONFIGURED
    log_level = log_level.upper()

    if not _LOGGING_CONFIGURED:
        _configure_root_handlers(log_level, log_file)

        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        _LOGGING_CONFIGURED = True

    _configure_third_party_loggers(log_level)
    return structlog.get_logger()


def get_uvicorn_log_config(
    log_level: str = "INFO", *, log_file: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """Return a Uvicorn-compatible logging config that integrates with structlog.

    Logs to stderr (not stdout -- consistent with `get_python_logger`,
    even though stdout isn't protocol-sensitive for the HTTP transport
    the way it is for stdio). `log_file`: optionally also write full-
    detail (DEBUG+) logs to this path.
    """
    log_level = log_level.upper()
    default_formatter = {
        "()": "structlog.stdlib.ProcessorFormatter",
        "processor": structlog.processors.JSONRenderer(),
        "foreign_pre_chain": [
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
        ],
    }

    handler_names = ["default"] + (["file"] if log_file else [])

    def make_logger_config(names: List[str], level: str) -> Dict[str, Any]:
        return {
            name: {
                "handlers": handler_names,
                "level": level,
                "propagate": False,
            }
            for name in names
        }

    # Base uvicorn loggers
    base_loggers = ["", "uvicorn", "uvicorn.error", "uvicorn.asgi", "uvicorn.protocols"]
    access_loggers = ["uvicorn.access"]

    handlers: Dict[str, Any] = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    }
    if log_file:
        handlers["file"] = {
            "formatter": "default",
            "class": "logging.FileHandler",
            "filename": str(log_file),
            "level": "DEBUG",
        }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": default_formatter,
            "access": default_formatter,
        },
        "handlers": handlers,
        "loggers": {
            **make_logger_config(base_loggers, log_level),
            **make_logger_config(access_loggers, log_level),
            **make_logger_config(
                list(THIRD_PARTY_LOGGERS - ERROR_ONLY_LOGGERS), log_level
            ),
            **make_logger_config(list(ERROR_ONLY_LOGGERS), "ERROR"),
        },
    }
