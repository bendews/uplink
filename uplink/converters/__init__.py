# Standard library imports
import collections
import functools

# Local imports
from uplink.converters import keys
from uplink.converters.interfaces import ConverterFactory, Converter
from uplink.converters.register import (
    get_default_converter_factories,
    register_default_converter_factory,
)

# Default converters - load standard first so it's ensured to be the
# last in the converter chain.
# fmt: off
from uplink.converters.standard import StandardConverter
from uplink.converters.marshmallow_ import MarshmallowConverter
from uplink.converters.typing_ import TypingConverter
# fmt: on

__all__ = [
    "StandardConverter",
    "MarshmallowConverter",
    "TypingConverter",
    "get_default_converter_factories",
    "register_default_converter_factory",
    "ConverterFactory",
    "Converter",
    "keys",
]


install = register_default_converter_factory
"""
Registers the given converter as a default converter, meaning the
converter will be included automatically with any consumer instance
and doesn't need to be explicitly provided through the ``converter``
parameter to be used.
"""


class ConverterChain(object):
    def __init__(self, converter_factory):
        self._converter_factory = converter_factory

    def __call__(self, *args, **kwargs):
        converter = self._converter_factory(*args, **kwargs)
        if isinstance(converter, Converter):
            converter.set_chain(self)
        return converter


class ConverterFactoryRegistry(collections.Mapping):
    """
    A registry that chains together
    :py:class:`interfaces.ConverterFactory` instances.

    When queried for a factory that can handle a particular converter
    type (e.g., ``keys.CONVERT_TO_REQUEST_BODY``), the registry
    traverses the chain until it finds a converter factory that can
    handle the request (i.e., the type's associated method returns a
    value other than ``None``).

    Here's an example -- it's contrived but effectively details the
    expected pattern of usage::

        # Create a registry with a single factory in its chain.
        registry = ConverterFactoryRegistry((StandardConverter,))

        # Get a callable that returns converters for turning arbitrary
        # objects into strings.
        get_str_converter_for_type = registry[keys.CONVERT_TO_STRING]

        # Traverse the chain to find a converter that can handle
        # converting ints into strings.
        converter = get_str_converter_for_type(int)

    Args:
        factories: An iterable of converter factories. Factories that
            appear earlier in the chain are given the opportunity to
            handle a request before those that appear later.
    """

    #: A mapping of keys to callables. Each callable value accepts a
    #: single argument, a :py:class:`interfaces.ConverterFactory`
    #: subclass, and returns another callable, which should return a
    #: :py:`interfaces.Converter` instance.
    _converter_factory_registry = {}

    def __init__(self, factories=(), *args, **kwargs):
        self._factories = tuple(factories)
        self._args = args
        self._kwargs = kwargs

    @property
    def factories(self):
        """
        Yields the registry's chain of converter factories, in order.
        """
        return iter(self._factories)

    def _make_chain_for_func(self, func):
        def chain(*args, **kwargs):
            for factory in self.factories:
                converter = func(factory)(*args, **kwargs)
                if callable(converter):
                    return converter

        return ConverterChain(
            functools.partial(chain, *self._args, **self._kwargs)
        )

    def _make_chain_for_key(self, converter_key):
        return self._make_chain_for_func(
            self._converter_factory_registry[converter_key]
        )

    def __getitem__(self, converter_key):
        """
        Retrieves a callable that creates converters for the type
        associated to the given key.

        If the given key is a callable, it will be recursively invoked
        to retrieve the final callable. See :py:class:`keys.Map` for
        an example of such a key. These callable keys should accept a
        single argument, a :py:class:`ConverterFactoryRegistry`.
        """
        if callable(converter_key):
            return converter_key(self)
        else:
            return self._make_chain_for_key(converter_key)

    def __len__(self):
        return len(self._converter_factory_registry)

    def __iter__(self):
        return iter(self._converter_factory_registry)

    @classmethod
    def register(cls, converter_key):
        """
        Returns a decorator that can be used to register a callable for
        the given ``converter_key``.
        """

        def wrapper(func):
            cls._converter_factory_registry[converter_key] = func
            return func

        return wrapper


@ConverterFactoryRegistry.register(keys.CONVERT_TO_REQUEST_BODY)
def make_request_body_converter(factory):
    return factory.make_request_body_converter


@ConverterFactoryRegistry.register(keys.CONVERT_FROM_RESPONSE_BODY)
def make_response_body_converter(factory):
    return factory.make_response_body_converter


@ConverterFactoryRegistry.register(keys.CONVERT_TO_STRING)
def make_string_converter(factory):
    return factory.make_string_converter
