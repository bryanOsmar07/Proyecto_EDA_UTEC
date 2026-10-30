
import pickle
from pathlib import Path

from src.bplus_tree import BPlusTree


def save_bplus_tree(tree, filepath):
    """
    Guarda una instantánea de la B+Tree en disco.
    Solo usar con archivos confiables del proyecto.
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with filepath.open("wb") as file:
        pickle.dump(tree, file, protocol=pickle.HIGHEST_PROTOCOL)

    return filepath


def load_bplus_tree(filepath):
    """
    Recupera una B+Tree previamente serializada.

    Nunca cargar archivos pickle de fuentes
    desconocidas o no confiables.
    """
    filepath = Path(filepath)

    with filepath.open("rb") as file:
        tree = pickle.load(file)

    if not isinstance(tree, BPlusTree):
        raise TypeError("El archivo no contiene una BPlusTree")

    return tree
