from Core.Identity import Identity


class Epsilon:
    """Núcleo principal de Epsilon."""

    def __init__(self) -> None:
        self.identity = Identity()

    def describe(self) -> str:
        return (
            f"Nombre: {self.identity.name}\n"
            f"Rol: {self.identity.role}\n"
            f"Propósito: {self.identity.purpose}"
        )


if __name__ == "__main__":
    epsilon = Epsilon()

    print("Epsilon iniciado correctamente.\n")
    print(epsilon.describe())