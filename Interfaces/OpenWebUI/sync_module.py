from abc import ABC, abstractmethod


class SyncModule(ABC):
    name: str = "Unnamed module"

    @abstractmethod
    def sync(self, dry_run: bool = True) -> bool:
        """Compare or synchronize this module.

        dry_run=True must not modify Open WebUI.
        """
        raise NotImplementedError