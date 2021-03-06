from unittest.mock import patch
from typing import NamedTuple

from dffml.base import config
from dffml.util.cli.arg import Arg, parse_unknown
from dffml.util.entrypoint import entrypoint
from dffml.df.types import Definition, DataFlow, Input
from dffml.df.base import op, BaseKeyValueStore
from dffml.df.memory import (
    MemoryKeyValueStore,
    MemoryRedundancyChecker,
    MemoryRedundancyCheckerConfig,
    MemoryOrchestrator,
)
from dffml.util.asynctestcase import AsyncTestCase


@config
class KeyValueStoreWithArgumentsConfig:
    filename: str


@entrypoint("withargs")
class KeyValueStoreWithArguments(BaseKeyValueStore):

    CONTEXT = NotImplementedError
    CONFIG = KeyValueStoreWithArgumentsConfig

    def __call__(self):
        raise NotImplementedError


def load_kvstore_with_args(loading=None):
    if loading == "withargs":
        return KeyValueStoreWithArguments
    return [KeyValueStoreWithArguments]


class TestMemoryRedundancyChecker(AsyncTestCase):
    @patch.object(BaseKeyValueStore, "load", load_kvstore_with_args)
    def test_args(self):
        self.assertDictEqual(
            MemoryRedundancyChecker.args({}),
            {
                "rchecker": {
                    "plugin": None,
                    "config": {
                        "memory": {
                            "plugin": None,
                            "config": {
                                "kvstore": {
                                    "plugin": Arg(
                                        type=load_kvstore_with_args,
                                        help="Key value store to use",
                                        default=MemoryKeyValueStore(),
                                    ),
                                    "config": {},
                                }
                            },
                        }
                    },
                }
            },
        )

    async def test_config_default_label(self):
        with patch.object(BaseKeyValueStore, "load", load_kvstore_with_args):
            was = MemoryRedundancyChecker.config(
                await parse_unknown(
                    "--rchecker-memory-kvstore",
                    "withargs",
                    "--rchecker-memory-kvstore-withargs-filename",
                    "somefile",
                )
            )
            self.assertEqual(type(was), MemoryRedundancyCheckerConfig)
            self.assertEqual(type(was.kvstore), KeyValueStoreWithArguments)
            self.assertEqual(
                type(was.kvstore.config), KeyValueStoreWithArgumentsConfig
            )
            self.assertEqual(was.kvstore.config.filename, "somefile")


CONDITION = Definition(name="condition", primitive="boolean")


class TestMemoryOrchestrator(AsyncTestCase):
    async def test_condition_does_run(self):
        ran = []

        @op(conditions=[CONDITION])
        async def condition_test(hi: str):
            ran.append(True)

        async with MemoryOrchestrator() as orchestrator:
            async with orchestrator(DataFlow(condition_test)) as octx:
                async for _ in octx.run(
                    [
                        Input(
                            value=True,
                            definition=condition_test.op.inputs["hi"],
                        ),
                        Input(value=True, definition=CONDITION),
                    ]
                ):
                    pass

        self.assertTrue(ran)

    async def test_condition_does_not_run(self):
        ran = []

        @op(conditions=[CONDITION])
        async def condition_test(hi: str):
            ran.append(True)

        async with MemoryOrchestrator() as orchestrator:
            async with orchestrator(DataFlow(condition_test)) as octx:
                async for _ in octx.run(
                    [
                        Input(
                            value=True,
                            definition=condition_test.op.inputs["hi"],
                        ),
                    ]
                ):
                    pass

        self.assertFalse(ran)

    async def test_condition_does_not_run_auto_start(self):
        ran = []

        @op(conditions=[CONDITION])
        async def condition_test():
            ran.append(True)  # pragma: no cover

        async with MemoryOrchestrator() as orchestrator:
            async with orchestrator(DataFlow(condition_test)) as octx:
                async for _ in octx.run([]):
                    pass

        self.assertFalse(ran)
