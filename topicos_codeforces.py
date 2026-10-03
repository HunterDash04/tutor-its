"""
topicos_codeforces.py — categorías temáticas del ITS construidas sobre las etiquetas
REALES que Codeforces asigna a cada problema.

Cada etiqueta original se agrupa en una categoría macro (solo se agrupa vocabulario;
no se inventa ninguna relación). Un problema puede pertenecer a varias categorías
porque Codeforces le asigna varias etiquetas.
"""

CATEGORIAS = [
    'Implementación y Simulación',
    'Algoritmos Voraces',
    'Matemáticas y Teoría de Números',
    'Programación Dinámica',
    'Estructuras de Datos',
    'Ordenamiento y Búsqueda',
    'Grafos',
    'Árboles',
    'Cadenas de Texto',
    'Manipulación de Bits',
    'Geometría y Juegos',
]

ETIQUETA_A_CATEGORIA = {
    'implementation': 'Implementación y Simulación',
    'brute force': 'Implementación y Simulación',
    'interactive': 'Implementación y Simulación',
    'schedules': 'Implementación y Simulación',
    'greedy': 'Algoritmos Voraces',
    'constructive algorithms': 'Algoritmos Voraces',
    'math': 'Matemáticas y Teoría de Números',
    'number theory': 'Matemáticas y Teoría de Números',
    'combinatorics': 'Matemáticas y Teoría de Números',
    'probabilities': 'Matemáticas y Teoría de Números',
    'matrices': 'Matemáticas y Teoría de Números',
    'chinese remainder theorem': 'Matemáticas y Teoría de Números',
    'fft': 'Matemáticas y Teoría de Números',
    'dp': 'Programación Dinámica',
    'divide and conquer': 'Programación Dinámica',
    'data structures': 'Estructuras de Datos',
    'dsu': 'Estructuras de Datos',
    'hashing': 'Estructuras de Datos',
    'sortings': 'Ordenamiento y Búsqueda',
    'binary search': 'Ordenamiento y Búsqueda',
    'two pointers': 'Ordenamiento y Búsqueda',
    'ternary search': 'Ordenamiento y Búsqueda',
    'meet-in-the-middle': 'Ordenamiento y Búsqueda',
    'graphs': 'Grafos',
    'dfs and similar': 'Grafos',
    'shortest paths': 'Grafos',
    'flows': 'Grafos',
    'graph matchings': 'Grafos',
    '2-sat': 'Grafos',
    'trees': 'Árboles',
    'strings': 'Cadenas de Texto',
    'string suffix structures': 'Cadenas de Texto',
    'expression parsing': 'Cadenas de Texto',
    'bitmasks': 'Manipulación de Bits',
    'geometry': 'Geometría y Juegos',
    'games': 'Geometría y Juegos',
}


def categorias_de(etiquetas):
    """'dp;greedy;math' -> ['Programación Dinámica', 'Algoritmos Voraces', ...] (sin repetir)."""
    if not isinstance(etiquetas, str) or not etiquetas:
        return []
    vistas = []
    for t in etiquetas.split(';'):
        c = ETIQUETA_A_CATEGORIA.get(t.strip())
        if c and c not in vistas:
            vistas.append(c)
    return vistas


def url_problema(id_problema):
    """'2267D' -> enlace al enunciado oficial en Codeforces."""
    i = 0
    while i < len(id_problema) and id_problema[i].isdigit():
        i += 1
    return f'https://codeforces.com/problemset/problem/{id_problema[:i]}/{id_problema[i:]}'
