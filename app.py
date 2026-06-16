# ==============================================================================
# 0. BOOTSTRAP: AUTO-INSTALADOR DE DEPENDENCIAS
# Responsabilidad: Instalar librerías externas automáticamente en el entorno local antes de la ejecución principal.
# ==============================================================================
import sys
import subprocess
import os

def _verificar_e_instalar_dependencias() -> None:
    """Verifica la existencia de dependencias clave e invoca a pip si es necesario."""
    # Diccionario de dependencias: { 'nombre_modulo_interno': 'nombre_paquete_pip' }
    dependencias = {
        "streamlit": "streamlit",
        "pandas": "pandas",
        "PIL": "Pillow",
        "numpy": "numpy",
        "cv2": "opencv-python",
        "openpyxl": "openpyxl",
        "xlsxwriter": "xlsxwriter"
    }

    faltantes = []
    for modulo, paquete in dependencias.items():
        try:
            __import__(modulo)
        except ImportError:
            faltantes.append(paquete)

    if faltantes:
        print(f"⏳ Entorno incompleto detectado. Instalando: {', '.join(faltantes)}")
        try:
            # Ejecuta pip install usando el ejecutable actual de Python
            subprocess.check_call([sys.executable, "-m", "pip", "install", *faltantes])
            print("✅ Instalación completada. Reiniciando proceso...")
            # Reinicia el script actual para recargar los módulos recién instalados en memoria
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except subprocess.CalledProcessError as e:
            print(f"❌ Error crítico en auto-setup al invocar pip: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Excepción general en auto-setup: {e}")
            sys.exit(1)


_verificar_e_instalar_dependencias()

# ==============================================================================
# 1. CONFIGURACIÓN E INICIALIZACIÓN DEL ENTORNO
# Explicación: Importa librerías, define constantes globales y aplica un filtro de logs estricto para suprimir advertencias en Colab.
# ==============================================================================

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import random
from collections import defaultdict
import io
import sys
import unicodedata
import hashlib
import time
from datetime import datetime
import json
import os
import warnings
import logging
import base64

# 1.1 Supresión agresiva de advertencias en Google Colab
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
class NoScriptRunContextFilter(logging.Filter):
    def filter(self, record):
        return "missing ScriptRunContext" not in record.getMessage()

for logger_name in logging.root.manager.loggerDict:
    if "streamlit" in logger_name:
        logging.getLogger(logger_name).addFilter(NoScriptRunContextFilter())

# 1.2 Configuración de Sistema
sys.setrecursionlimit(3000)

# 1.3 Configuración de Rutas y Carpetas
# Responsabilidad: Construir un directorio de persistencia local dinámico encriptando la ruta absoluta del script para evadir WinError 5.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_TORNEOS = os.path.join(BASE_DIR, "Catan_Torneos")
if not os.path.exists(CARPETA_TORNEOS):
    try:
        os.makedirs(CARPETA_TORNEOS)
        print(f"✅ Carpeta de persistencia creada en: {CARPETA_TORNEOS}")
    except Exception as e:
        print(f"⚠️ Alerta I/O: Fallo local. Causa: {str(e)}. Fallback a Documentos de usuario.")
        CARPETA_TORNEOS = os.path.join(os.path.expanduser("~"), "Documents", "Catan_Torneos")
        os.makedirs(CARPETA_TORNEOS, exist_ok=True)

# 1.4 Constantes Globales
CONSTANTS = {
    'MIN_PLAYERS': 4,
    'MAX_PLAYERS': 100,
    'BT_NODE_BUDGET': 500000,
    'MIN_PM': 2,
    'MAX_PM': 10,
    'AUTOSAVE_FILE': os.path.join(CARPETA_TORNEOS, 'torneo_actual.json'),
    'BET_AMOUNTS': [1000, 2000, 5000, 10000, 20000],
    'PAYOUT_MAX_CAP': 3.5,
    'PAYOUT_GLOBAL_FLOOR': 1.2,
    'PRESSURE_STEP': 0.05,
    'FLOORS_BY_RANK_BASE': {
        0: 1.5,
        1: 1.8,
        2: 2.2,
        3: 3.0
    }
}

# ==============================================================================
# 2. LÓGICA DE NEGOCIO (CLASE TORNEOMANAGER)
# Explicación: Contiene toda la lógica del torneo, jugadores, rondas, apuestas y persistencia.
# ==============================================================================

class TorneoManager:
    # 2.1 Inicialización y Estado
    # Explicación: Define atributos iniciales, el generador aleatorio interno y el sistema de caché de estado.
    def __init__(self):
        self._rng = random.Random()
        self.tournament_name = ""
        self.players = []
        self.eliminated_players = set()
        self.player_teams = {}
        self.teams = defaultdict(list)
        self.rounds = []
        self.results = {}
        self.player_history = defaultdict(set)
        self.player_positions = defaultdict(set)
        self.tournament_type = None
        self.phase = 'clasificatoria'
        self.semifinal_tables = {i: [] for i in range(1, 5)}
        self.final_table = []
        self.semifinal_results = {}
        self.final_results = {}
        self.seeds_fase_final = {}
        self.last_round_generation_msg = ""
        self.player_count_changes_log = []
        self.bets = []
        self.betting_open = False
        self.betting_results_log = []
        self.house_bankroll = 10000
        self.maps = {}
        self._history_signature_cache = None
        self._history_dirty = True

    # 2.2 Persistencia (Guardar y Cargar)
    # Explicación: Convierte el estado a diccionario, guarda en JSON y carga desde archivo.
    def to_dict(self):
        results_str_keys = {f"{k[0]}_{k[1]}": v for k, v in self.results.items()}
        history_list = {k: list(v) for k, v in self.player_history.items()}
        positions_list = {k: list(v) for k, v in self.player_positions.items()}
        eliminated_list = list(self.eliminated_players)
        return {
            "tournament_name": self.tournament_name,
            "players": self.players,
            "eliminated_players": eliminated_list,
            "player_teams": self.player_teams,
            "teams": {k: list(v) for k,v in self.teams.items()},
            "rounds": self.rounds,
            "results": results_str_keys,
            "player_history": history_list,
            "player_positions": positions_list,
            "tournament_type": self.tournament_type,
            "phase": self.phase,
            "semifinal_tables": self.semifinal_tables,
            "final_table": self.final_table,
            "semifinal_results": self.semifinal_results,
            "final_results": self.final_results,
            "seeds_fase_final": self.seeds_fase_final,
            "last_round_generation_msg": self.last_round_generation_msg,
            "player_count_changes_log": self.player_count_changes_log,
            "bets": self.bets,
            "betting_open": self.betting_open,
            "betting_results_log": self.betting_results_log,
            "house_bankroll": self.house_bankroll,
            "maps": self.maps
        }

    def save_state(self):
        try:
            data = self.to_dict()
            with open(CONSTANTS['AUTOSAVE_FILE'], 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            if self.tournament_name:
                clean_name = "".join([c for c in self.tournament_name if c.isalnum() or c in (' ','_')]).strip().replace(" ", "_")
                date_str = datetime.now().strftime("%Y-%m-%d")
                filename = f"{clean_name}_{date_str}.json"
                path_historico = os.path.join(CARPETA_TORNEOS, filename)
                with open(path_historico, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"Error Auto-Save: {e}")
            return False

    def load_state(self, specific_path=None):
        target_file = specific_path if specific_path else CONSTANTS['AUTOSAVE_FILE']
        if not os.path.exists(target_file):
            return False, "No existe archivo de respaldo."
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.tournament_name = data.get("tournament_name", "")
            self.players = data.get("players", [])
            self.eliminated_players = set(data.get("eliminated_players", []))
            self.player_teams = data.get("player_teams", {})
            self.teams = defaultdict(list, data.get("teams", {}))
            self.rounds = data.get("rounds", [])
            self.results = {}
            for k_str, v in data.get("results", {}).items():
                r, t = map(int, k_str.split('_'))
                self.results[(r, t)] = v
            self.player_history = defaultdict(set)
            for k, v_list in data.get("player_history", {}).items():
                self.player_history[k] = set(v_list)
            self.player_positions = defaultdict(set)
            for k, v_list in data.get("player_positions", {}).items():
                self.player_positions[k] = set(v_list)
            self.tournament_type = data.get("tournament_type")
            self.phase = data.get("phase", 'clasificatoria')
            semi_tables_raw = data.get("semifinal_tables", {})
            self.semifinal_tables = {int(k): v for k, v in semi_tables_raw.items()}
            for i in range(1, 5):
                if i not in self.semifinal_tables: self.semifinal_tables[i] = []
            self.final_table = data.get("final_table", [])
            semi_results_raw = data.get("semifinal_results", {})
            self.semifinal_results = {int(k): v for k, v in semi_results_raw.items()}
            self.final_results = data.get("final_results", {})
            self.seeds_fase_final = data.get("seeds_fase_final", {})
            self.last_round_generation_msg = data.get("last_round_generation_msg", "")
            self.player_count_changes_log = data.get("player_count_changes_log", [])
            self.bets = data.get("bets", [])
            self.betting_open = data.get("betting_open", False)
            self.betting_results_log = data.get("betting_results_log", [])
            self.house_bankroll = data.get("house_bankroll", 10000)
            self.maps = data.get("maps", {})
            self._history_dirty = True
            return True, "Estado recuperado exitosamente."
        except Exception as e:
            return False, f"Error al cargar respaldo: {e}"

    # 2.3 Utilidades Internas
    # Explicación: Normalización de nombres, reconstrucción de equipos, configuración de mesas y optimización de hashing.
    def _normalizar_nombre(self, texto):
        if not isinstance(texto, str): return texto
        texto = unicodedata.normalize('NFD', texto)
        texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
        return texto.upper().strip()

    def _rebuild_teams_from_players(self):
        self.teams = defaultdict(list)
        for p in self.players:
            if p['team']:
                self.teams[p['team']].append(p['name'])

    def _table_config(self, n):
        if n < CONSTANTS['MIN_PLAYERS']: return []
        r = n % 4
        if r == 0: return [4] * (n // 4)
        if r == 1: return [4] * ((n - 9) // 4) + [3, 3, 3]
        if r == 2: return [4] * ((n - 6) // 4) + [3, 3]
        return [4] * (n // 4) + [3]

    def _team_size(self, team):
        return len([p for p in self.players if p['team'] == team]) if team else 0

    def _team_limit_for_table(self, team):
        ts = self._team_size(team)
        if ts == 0: return 10**9
        return 1 if ts <= 3 else 2

    def _history_signature(self):
        if not self._history_dirty and self._history_signature_cache is not None:
            return self._history_signature_cache
        items = sorted((a, tuple(sorted(list(b)))) for a, b in self.player_history.items() if b)
        payload = repr(items).encode('utf-8')
        self._history_signature_cache = hashlib.sha256(payload).hexdigest()[:8]
        self._history_dirty = False
        return self._history_signature_cache

    def _derive_seed(self, round_idx):
        roster = '|'.join(sorted(f"{p['name']}#{p['team'] or ''}" for p in self.players))
        key = f"{roster}|r:{round_idx}|t:{self.tournament_type}|h:{self._history_signature()}"
        return int(hashlib.sha256(key.encode('utf-8')).hexdigest()[:8], 16)

    # 2.4 Gestión de Jugadores (CRUD)
    # Explicación: Agrega, elimina, edita y carga jugadores desde DataFrame, regenerando rondas si es necesario.
    def agregar_jugador(self, nombre, equipo=''):
        if self.phase != 'clasificatoria': return False, "Inscripción cerrada."
        if len(self.players) >= CONSTANTS['MAX_PLAYERS']: return False, f"Límite de {CONSTANTS['MAX_PLAYERS']} alcanzado."
        nombre = self._normalizar_nombre(nombre)
        if equipo:
            equipo_str = str(equipo).strip().upper()
            equipo = "" if equipo_str == 'NAN' else equipo_str
        else: equipo = ""
        if not nombre: return False, "Nombre vacío."
        if any(p['name'] == nombre for p in self.players): return False, "Nombre duplicado."
        self.players.append({'name': nombre, 'team': equipo})
        self.player_teams[nombre] = equipo
        self._rebuild_teams_from_players()
        if self.rounds: self.player_count_changes_log.append(f"Jugador {nombre} ingresó durante el torneo.")
        self._regenerar_desde(0)
        self.save_state()
        return True, f"Agregado: {nombre}"

    def eliminar_jugador(self, nombre):
        p_idx = next((i for i, p in enumerate(self.players) if p['name'] == nombre), None)
        if p_idx is None: return False, "No encontrado"
        self.eliminated_players.add(nombre)
        del self.players[p_idx]
        self._rebuild_teams_from_players()
        msg = f"Jugador {nombre} eliminado."
        if self.rounds: self.player_count_changes_log.append(f"Jugador {nombre} eliminado durante el torneo.")

        if self.phase == 'clasificatoria':
            self._regenerar_desde(0)
            self.save_state()
            return True, f"{msg} Rondas regeneradas."
        elif self.phase == 'semifinal':
            found_k = None
            for k, mesa in self.semifinal_tables.items():
                if nombre in mesa:
                    found_k = k
                    break
            if found_k:
                ranking_data = self._obtener_ranking_data()
                en_semis = [p for m in self.semifinal_tables.values() for p in m]
                candidates = [d['Jugador'] for d in ranking_data if d['Jugador'] not in self.eliminated_players and d['Jugador'] not in en_semis]
                if candidates:
                    replacement = candidates[0]
                    idx = self.semifinal_tables[found_k].index(nombre)
                    self.semifinal_tables[found_k][idx] = replacement
                    msg += f" Reemplazado en Semifinal {found_k} por {replacement}."
                    if found_k in self.semifinal_results: del self.semifinal_results[found_k]
                else: msg += " No hay suplentes disponibles."
        elif self.phase == 'final':
            if nombre in self.final_table:
                es_final_directa = not any(self.semifinal_tables.values())
                replacement = None
                method_msg = ""
                if es_final_directa:
                    ranking_data = self._obtener_ranking_data()
                    candidates = [d['Jugador'] for d in ranking_data if d['Jugador'] not in self.eliminated_players and d['Jugador'] not in self.final_table]
                    if candidates:
                        replacement = candidates[0]
                        method_msg = "(Siguiente en Tabla General)"
                else:
                    origin_semi = None
                    for k, mesa in self.semifinal_tables.items():
                        if nombre in mesa: origin_semi = k; break
                    if origin_semi and origin_semi in self.semifinal_results:
                        res = self.semifinal_results[origin_semi]
                        mesa = self.semifinal_tables[origin_semi]
                        def sort_key(p):
                            d = res.get(p, {'PV': 0, 'PM': 0})
                            seed = self.seeds_fase_final.get(p, 9999)
                            return (d['PV'], d['PM'], -seed)
                        sorted_p = sorted(mesa, key=sort_key, reverse=True)
                        suplentes = [p for p in sorted_p if p != nombre and p not in self.eliminated_players]
                        if suplentes:
                            replacement = suplentes[0]
                            method_msg = f"(2do lugar de Semifinal {origin_semi})"
                        else:
                            ranking_data = self._obtener_ranking_data()
                            cands = [d['Jugador'] for d in ranking_data if d['Jugador'] not in self.eliminated_players and d['Jugador'] not in self.final_table]
                            if cands: replacement = cands[0]; method_msg = "(Siguiente en Tabla - Emergencia)"
                if replacement:
                    idx = self.final_table.index(nombre)
                    self.final_table[idx] = replacement
                    msg += f" Reemplazado en Final por {replacement} {method_msg}."
                    self.final_results = {}
                else: msg += " No se encontró reemplazo válido."
        self.save_state()
        return True, msg

    # ==============================================================================
    # 2.4.1 Eliminación Masiva de Jugadores
    # Responsabilidad: Limpiar integralmente el registro de participantes y dependencias asociadas con validación estricta de fase.
    # ==============================================================================
    def eliminar_todos_los_jugadores(self) -> tuple[bool, str]:
        try:
            if self.phase != 'clasificatoria':
                return False, "No se pueden vaciar jugadores fuera de fase clasificatoria."
            self.players.clear()
            self.eliminated_players.clear()
            self.player_teams.clear()
            self.teams.clear()
            self.rounds.clear()
            self.results.clear()
            self.player_history.clear()
            self.player_positions.clear()
            self.player_count_changes_log.clear()
            self._history_dirty = True
            self.save_state()
            return True, "Todos los jugadores han sido eliminados de la base de datos."
        except Exception as e:
            return False, f"Error crítico al intentar vaciar la base de datos: {str(e)}"

    def editar_jugador(self, nombre_actual, nuevo_nombre, nuevo_equipo):
        p_idx = next((i for i, p in enumerate(self.players) if p['name'] == nombre_actual), None)
        if p_idx is None: return False, "Jugador no encontrado."
        nuevo_nombre = self._normalizar_nombre(nuevo_nombre)
        nuevo_equipo = str(nuevo_equipo).strip().upper() if nuevo_equipo else ""
        if nuevo_equipo == 'NAN': nuevo_equipo = ""
        if nuevo_nombre != nombre_actual:
            if any(p['name'] == nuevo_nombre for p in self.players): return False, "El nuevo nombre ya existe."
        if nombre_actual in self.player_history:
            self.player_history[nuevo_nombre] = self.player_history.pop(nombre_actual)
            self._history_dirty = True
        self.players[p_idx]['name'] = nuevo_nombre
        self.players[p_idx]['team'] = nuevo_equipo
        if nombre_actual in self.player_teams: del self.player_teams[nombre_actual]
        self.player_teams[nuevo_nombre] = nuevo_equipo
        self._rebuild_teams_from_players()
        self.save_state()
        return True, f"Editado: {nuevo_nombre}"

    def cargar_desde_dataframe(self, df):
        cols_map = {c: str(c).lower().strip() for c in df.columns}
        name_col = next((k for k,v in cols_map.items() if 'nombre' in v or 'jugador' in v or 'name' in v), None)
        team_col = next((k for k,v in cols_map.items() if 'equipo' in v or 'team' in v), None)
        if not name_col: return False, "No se encontró columna de Nombre."
        count = 0
        for _, row in df.iterrows():
            if len(self.players) >= CONSTANTS['MAX_PLAYERS']: break
            raw_name = str(row.get(name_col, '')).strip()
            if not raw_name or raw_name.lower() == 'nan': continue
            team = ''
            if team_col:
                raw_team = str(row.get(team_col, '')).strip().upper()
                if raw_team != 'NAN': team = raw_team if len(raw_team) < 15 else raw_team[:10]
            ok, _ = self.agregar_jugador(raw_name, team)
            if ok: count += 1
        self.save_state()
        return True, f"Cargados {count} jugadores."

    # 2.5 Motor de Emparejamiento (Algoritmos)
    # Explicación: Verifica restricciones, genera mesas con iteración en pila (Stack) y relajación progresiva.
    def _check_round_constraints(self, tables, r_label="?"):
        issues = []
        for i, mesa in enumerate(tables):
            teams_in_table = defaultdict(int)
            for p in mesa:
                t = self.player_teams.get(p, '')
                if t: teams_in_table[t] += 1
            for t, count in teams_in_table.items():
                limit = self._team_limit_for_table(t)
                if count > limit:
                    issues.append(f"Ronda {r_label} - Mesa {i+1}: Equipo {t} tiene {count} jugadores (Max permitido: {limit}).")
            mesa_set = set(mesa)
            for p in mesa:
                rivals = self.player_history.get(p, set())
                current_rivals = mesa_set - {p}
                if current_rivals.intersection(rivals):
                    issues.append(f"Ronda {r_label} - Mesa {i+1}: {p} repite contra {', '.join(current_rivals.intersection(rivals))}.")
        return list(set(issues))

    def _generar_ronda_constraints(self, table_sizes, r_label="?", is_p16=False):
        active = [p['name'] for p in self.players]
        self._rng.shuffle(active)
        collision_counts = defaultdict(int)
        for r in self.rounds:
            if r.get('tables'):
                for table in r['tables']:
                    for i in range(len(table)):
                        for j in range(i + 1, len(table)):
                            p1, p2 = sorted((table[i], table[j]))
                            collision_counts[(p1, p2)] += 1

        def score(n):
            team = self.player_teams.get(n, '')
            ts = self._team_size(team)
            hist_len = len(self.player_history.get(n, ()))
            return (-(1 if team else 0), -ts, -hist_len)

        candidates = sorted(active, key=score)
        tables = [[] for _ in table_sizes]
        team_counts = [defaultdict(int) for _ in table_sizes]
        nodes = [0]
        positions = [t_idx for t_idx, size in enumerate(table_sizes) for _ in range(size)]

        def can_place(name, t_idx, relax_level):
            if len(tables[t_idx]) >= table_sizes[t_idx]: return False
            if is_p16 and relax_level <= 2:
                current_pos = len(tables[t_idx])
                if current_pos in self.player_positions.get(name, set()):
                    return False
            if relax_level == 0:
                team = self.player_teams.get(name, '')
                if team:
                    limit = self._team_limit_for_table(team)
                    if team_counts[t_idx][team] >= limit: return False
            current_table_members = tables[t_idx]
            if relax_level <= 1:
                rivals = self.player_history.get(name, set())
                if any(mate in rivals for mate in current_table_members): return False
            if relax_level == 2:
                 for mate in current_table_members:
                    p1, p2 = sorted((name, mate))
                    if collision_counts[(p1, p2)] >= 2: return False
            return True

        def backtrack(relax_level):
            if not positions: return True

            def get_candidates(p_idx):
                t_idx = positions[p_idx]
                free = [c for c in candidates if c not in {p for tbl in tables for p in tbl}]
                free_copy = free[:]
                self._rng.shuffle(free_copy)
                def local_cost(name):
                    team = self.player_teams.get(name, '')
                    tc = team_counts[t_idx][team]
                    hist_conf = sum(1 for m in tables[t_idx] if m in self.player_history.get(name, ()))
                    return (-tc, hist_conf)
                free_copy.sort(key=local_cost)
                return free_copy

            stack = [[0, get_candidates(0), 0]]

            while stack:
                nodes[0] += 1
                if nodes[0] > CONSTANTS['BT_NODE_BUDGET']: return False

                frame = stack[-1]
                p_idx, cands, c_idx = frame[0], frame[1], frame[2]
                t_idx = positions[p_idx]

                if c_idx < len(cands):
                    name = cands[c_idx]
                    frame[2] += 1

                    if can_place(name, t_idx, relax_level):
                        tables[t_idx].append(name)
                        team = self.player_teams.get(name, '')
                        if team: team_counts[t_idx][team] += 1

                        if p_idx + 1 == len(positions):
                            return True

                        stack.append([p_idx + 1, get_candidates(p_idx + 1), 0])
                else:
                    stack.pop()
                    if stack:
                        parent_frame = stack[-1]
                        parent_t_idx = positions[parent_frame[0]]
                        placed_name = tables[parent_t_idx].pop()
                        team = self.player_teams.get(placed_name, '')
                        if team: team_counts[parent_t_idx][team] -= 1

            return False

        success = False
        final_relax_level = 0
        candidates_original_order = candidates[:]

        for relax in (0, 1, 2, 3):
            max_intentos = 5 if relax == 0 else 1
            for intento in range(max_intentos):
                if relax == 0:
                    if intento > 0:
                        self._rng.shuffle(candidates)
                    else:
                        candidates = candidates_original_order[:]
                for tbl in tables: tbl.clear()
                for tc in team_counts: tc.clear()
                nodes[0] = 0
                if backtrack(relax):
                    success = True
                    final_relax_level = relax
                    break
            if success:
                break

        if not success:
            self._rng.shuffle(active)
            tables = [[] for _ in table_sizes]
            curr = 0
            for i, size in enumerate(table_sizes):
                for _ in range(size):
                    if curr < len(active):
                        tables[i].append(active[curr])
                        curr += 1
            final_relax_level = 3

        issues = self._check_round_constraints(tables, r_label)

        if final_relax_level == 0: self.last_round_generation_msg = f"✅ Ronda {r_label}: Generada PERFECTA."
        elif final_relax_level == 1: self.last_round_generation_msg = f"⚠️ Ronda {r_label}: Ignorando EQUIPOS (Rivales únicos)."
        elif final_relax_level == 2: self.last_round_generation_msg = f"⚠️ Ronda {r_label}: Permitiendo REPETIR RIVALES (Max 1 repetición)."
        else:
            self.last_round_generation_msg = f"⚠️ Ronda {r_label}: ALEATORIA (No se pudieron cumplir reglas)."
            if issues: self.last_round_generation_msg += "\n" + "\n".join(issues[:3])

        for t in tables:
            for pos, a in enumerate(t):
                self.player_history[a].update(set(t) - {a})
                self._history_dirty = True
                if is_p16:
                    self.player_positions[a].add(pos)

        return tables

    # 2.6 Sistema Suizo
    # Explicación: Genera ranking y empareja fuertes vs fuertes según puntuación actual.
    def _obtener_ranking_data(self):
        activos = {p['name'] for p in self.players}
        data = []
        raw_stats = defaultdict(lambda: {'PV': 0.0, 'PM': 0.0, '%V_sum': 0.0, 'N': 0, '2do': 0, '3ro': 0})
        for mesa in self.results.values():
           for name, st in mesa.items():
                entry = raw_stats[name]
                entry['PV'] += st.get('PV', 0)
                entry['PM'] += st.get('PM', 0)
                entry['%V_sum'] += st.get('%V', 0)
                entry['N'] += 1
                if st.get('P°') == 2: entry['2do'] += 1
                elif st.get('P°') == 3: entry['3ro'] += 1
        all_names = set(raw_stats.keys()) | activos
        for name in all_names:
            stats = raw_stats[name]
            data.append({
                'Jugador': name,
                'Activo': 1 if name in activos else 0,
                'Equipo': self.player_teams.get(name, ''),
                'PV': stats['PV'],
                'PM': stats['PM'],
                '%V': (stats['%V_sum'] / stats['N']) if stats['N'] else 0.0,
                '2dos': stats['2do'],
                '3ros': stats['3ro'],
                'PJ': stats['N']
            })
        return sorted(data, key=lambda x: (x['Activo'], x['PV'], x['PM'], x['%V'], x['2dos'], x['3ros']), reverse=True)

    def _generar_ronda_suiza(self, round_num):
        ranking = [d['Jugador'] for d in self._obtener_ranking_data() if d['Activo']]
        sizes = self._table_config(len(self.players))
        tables = []
        pool_iter = iter(ranking)
        for size in sizes:
            mesa = []
            while len(mesa) < size:
                try: mesa.append(next(pool_iter))
                except StopIteration: break
            tables.append(mesa)
        self.last_round_generation_msg = "✅ Ronda Suiza generada por Ranking (Fuerte vs Fuerte)."
        return tables

    # 2.7 Gestión de Rondas (General)
    # Explicación: Regenera rondas desde un índice, genera rondas iniciales y permite intercambios manuales actualizando historial.
    def _regenerar_desde(self, start_index):
        if start_index >= len(self.rounds): return
        self.player_history = defaultdict(set)
        self.player_positions = defaultdict(set)
        self._history_dirty = True
        for i in range(start_index):
            if self.rounds[i].get('played'):
                 is_p16_past = self.rounds[i].get('type') == 'aleatorio_p16'
                 for table in self.rounds[i]['tables']:
                    for pos, a in enumerate(table):
                        self.player_history[a].update(set(table) - {a})
                        if is_p16_past:
                            self.player_positions[a].add(pos)
        for idx in range(start_index, len(self.rounds)):
            if self.rounds[idx].get('played'): continue
            is_suizo = (self.tournament_type == 'suizo') and (idx > 0)
            is_p16 = (self.tournament_type == 'aleatorio_p16')
            if is_suizo:
                 if idx > 0 and self.rounds[idx-1].get('played'):
                      self.rounds[idx]['tables'] = self._generar_ronda_suiza(idx+1)
                      self.rounds[idx]['type'] = 'suizo'
                 else:
                      self.rounds[idx]['tables'] = []
            else:
                sizes = self._table_config(len(self.players))
                self._rng.seed(self._derive_seed(idx))
                self.rounds[idx]['tables'] = self._generar_ronda_constraints(sizes, r_label=idx+1, is_p16=is_p16)
                self.rounds[idx]['type'] = self.tournament_type

    def generar_rondas(self, n_rondas, tipo):
        if len(self.players) < CONSTANTS['MIN_PLAYERS']: return False, "Faltan jugadores"
        if tipo == 'aleatorio_p16' and len(self.players) < 16:
            return False, "El sistema 'Aleatorio P16' requiere un mínimo estricto de 16 jugadores."
        played_count = sum(1 for r in self.rounds if r.get('played'))
        if played_count > 0:
            current_total = len(self.rounds)
            if n_rondas > current_total:
                self.rounds.extend([{'tables': [], 'played': False} for _ in range(n_rondas - current_total)])
            elif n_rondas < current_total and n_rondas >= played_count:
                self.rounds = self.rounds[:n_rondas]
        else:
            self.rounds = [{'tables': [], 'played': False} for _ in range(n_rondas)]
        self.tournament_type = tipo
        self._regenerar_desde(played_count)
        self.save_state()
        return True, "Rondas generadas"

    def _reconstruir_historial(self):
        self.player_history = defaultdict(set)
        self.player_positions = defaultdict(set)
        self._history_dirty = True
        for r in self.rounds:
            if r.get('tables'):
                is_p16 = r.get('type') == 'aleatorio_p16'
                for table in r['tables']:
                    for pos, p in enumerate(table):
                        self.player_history[p].update(set(table) - {p})
                        if is_p16:
                            self.player_positions[p].add(pos)

    def intercambio_manual(self, ronda_num, mesa1_idx, p1, mesa2_idx, p2):
        try:
            r_idx = ronda_num - 1
            if r_idx < 0 or r_idx >= len(self.rounds): return False, "Ronda inválida."
            mesas = self.rounds[r_idx]['tables']
            m1, m2 = mesa1_idx - 1, mesa2_idx - 1
            if p1 not in mesas[m1]: return False, f"{p1} no está en Mesa {mesa1_idx}"
            if p2 not in mesas[m2]: return False, f"{p2} no está en Mesa {mesa2_idx}"
            idx_p1 = mesas[m1].index(p1)
            idx_p2 = mesas[m2].index(p2)
            mesas[m1][idx_p1] = p2
            mesas[m2][idx_p2] = p1
            self._reconstruir_historial()
            self.save_state()
            return True, f"Intercambio realizado: {p1} ↔ {p2}"
        except Exception as e:
            return False, f"Error al intercambiar: {e}"

    # 2.8 Resultados y Fases Finales
    # Explicación: Registra resultados de rondas, genera fases finales automáticas y permite deshacer.
    def registrar_resultados(self, round_num, table_num, scores_dict, manual_winner=None):
        mkey = (round_num, table_num)
        table = self.rounds[round_num-1]['tables'][table_num-1]
        pm_values = list(scores_dict.values())
        denom = sum(pm_values)
        if len(table) == 3: denom += int(sum(pm_values)/3.0)
        max_pm = max(pm_values)
        winners = [p for p, sc in scores_dict.items() if sc == max_pm]
        pv_map = {1: 1.0, 2: 0.5, 3: 0.3, 4: 0.25}
        assigned_pv = pv_map.get(len(winners), 0.0)
        self.results[mkey] = {}
        for p in table:
            pm = scores_dict[p]
            is_winner = (pm == max_pm)
            pv = assigned_pv if is_winner else 0.0
            if manual_winner and p == manual_winner: pv = 1.0
            elif manual_winner and p != manual_winner: pv = 0.0
            pct_v = (pm / denom * 100.0) if denom > 0 else 0.0
            self.results[mkey][p] = {'PM': pm, 'PV': pv, '%V': pct_v}
        def sort_key(p):
            d = self.results[mkey][p]
            return (d['PV'], d['PM'], d['%V'])
        sorted_players = sorted(table, key=sort_key, reverse=True)
        rank = 1
        for i, p in enumerate(sorted_players):
            if i > 0 and sort_key(p) != sort_key(sorted_players[i-1]):
                rank += 1
            self.results[mkey][p]['P°'] = rank
        mesas_totales = len(self.rounds[round_num-1]['tables'])
        mesas_jugadas = sum(1 for t in range(1, mesas_totales+1) if (round_num, t) in self.results)
        if mesas_jugadas == mesas_totales:
            self.rounds[round_num-1]['played'] = True
            if self.tournament_type == 'suizo': self._regenerar_desde(round_num)
            if all(r.get('played') for r in self.rounds) and self.phase == 'clasificatoria':
                self.generar_fase_final_auto()
        self.save_state()
        return True, "Resultados guardados"

    def generar_fase_final_auto(self, modo='auto'):
        played_count = sum(1 for r in self.rounds if r.get('played'))
        if played_count < 1:
            return False, "⚠️ Error: Debe haber al menos una ronda jugada para generar fases finales."
        ranking = [d['Jugador'] for d in self._obtener_ranking_data() if d['Activo']]
        n = len(ranking)
        self.seeds_fase_final = {name: i for i, name in enumerate(ranking)}
        target_phase = None
        if modo == 'auto':
            if n >= 29: target_phase = 'semifinal'
            elif n >= 12: target_phase = 'final'
            elif n >= 4: target_phase = 'final'
            else: return False, f"Insuficientes jugadores activos (Mínimo 4, tienes {n})"
        elif modo == 'semifinal':
            if n >= 16: target_phase = 'semifinal'
            else: return False, f"⚠️ Requisito no cumplido: Se necesitan mínimo 16 jugadores (Tienes {n})."
        elif modo == 'final':
            if n >= 8: target_phase = 'final'
            else: return False, f"⚠️ Requisito no cumplido: Se necesitan mínimo 8 jugadores (Tienes {n})."
        if target_phase == 'semifinal':
            self.phase = 'semifinal'
            top16 = ranking[:16]
            self.semifinal_tables = {
                1: [top16[0], top16[7], top16[8], top16[15]],
                2: [top16[1], top16[6], top16[9], top16[14]],
                3: [top16[2], top16[5], top16[10], top16[13]],
                4: [top16[3], top16[4], top16[11], top16[12]]
            }
            return True, "✅ Semifinales generadas (Top 16)"
        elif target_phase == 'final':
            self.phase = 'final'
            self.final_table = ranking[:4]
            return True, "✅ Final Directa generada (Top 4)"
        return False, "No se pudo determinar la fase."

    def deshacer_fase_final(self):
        self.phase = 'clasificatoria'
        self.semifinal_tables = {i: [] for i in range(1, 5)}
        self.final_table = []
        self.semifinal_results = {}
        self.final_results = {}
        self.seeds_fase_final = {}
        self.betting_open = False
        self.save_state()
        return True, "🔙 Regresado a Fase Clasificatoria."

    def registrar_resultados_finales(self, stage, table_id, scores, winner_override=None):
        if stage == 'final' and self.betting_open:
            return False, "⚠️ ERROR CRÍTICO: No puedes ingresar el resultado final mientras las apuestas sigan ABIERTAS. Ciérralas primero en la pestaña 'Apuestas'.", []
        if stage == 'semifinal':
            target_results = self.semifinal_results
            mesa = self.semifinal_tables[table_id]
        else:
            target_results = self.final_results
            mesa = self.final_table
        res_temp = {}
        for p in mesa: res_temp[p] = {'PM': scores[p]}
        max_pm = max(scores.values())
        ganadores = [p for p in mesa if scores[p] == max_pm]
        winner = winner_override
        if not winner and len(ganadores) == 1: winner = ganadores[0]
        if not winner:
            winner = min(ganadores, key=lambda x: self.seeds_fase_final.get(x, 999))
        for p in mesa:
            res_temp[p]['PV'] = 1.0 if p == winner else 0.0
            pm_vals = list(scores.values())
            denom = sum(pm_vals)
            res_temp[p]['%V'] = (scores[p]/denom*100) if denom else 0
        sorted_p = sorted(mesa, key=lambda x: (res_temp[x]['PV'], res_temp[x]['PM'], -self.seeds_fase_final.get(x,999)), reverse=True)
        for i, p in enumerate(sorted_p): res_temp[p]['P°'] = i + 1
        msgs_desempate = []
        for i in range(len(sorted_p) - 1):
            p1, p2 = sorted_p[i], sorted_p[i+1]
            d1, d2 = res_temp[p1], res_temp[p2]
            if d1['PM'] == d2['PM'] and d1['PV'] == d2['PV']:
                s1 = self.seeds_fase_final.get(p1, 999) + 1
                s2 = self.seeds_fase_final.get(p2, 999) + 1
                msgs_desempate.append(f"ℹ️ **{p1}** (#{s1}) gana posición a **{p2}** (#{s2}) por Ranking.")
        if stage == 'semifinal':
            self.semifinal_results[table_id] = res_temp
            if len(self.semifinal_results) == 4:
                finalistas = []
                for k in range(1, 5):
                    m_res = self.semifinal_results[k]
                    ganador = next((p for p, d in m_res.items() if d['PV'] == 1.0), None)
                    if ganador: finalistas.append(ganador)
                self.final_table = finalistas
                self.phase = 'final'
        else:
            self.final_results = res_temp
            self._liquidar_apuestas(winner)
        self.save_state()
        final_msg = f"Ganador: {winner}"
        return True, final_msg, msgs_desempate

    def reiniciar_apuestas(self):
        self.bets = []
        self.betting_results_log = []
        self.save_state()
        return True, "🗑️ Todas las apuestas han sido eliminadas."

    # 2.9 SISTEMA DE APUESTAS
    # Explicación: Abre/cierra apuestas, valida solvencia, calcula pisos dinámicos, odds y liquidación.
    def abrir_apuestas(self):
        if self.phase != 'final' or not self.final_table:
            return False, "Solo se pueden abrir apuestas en la Fase Final."
        self.betting_open = True
        self.save_state()
        return True, "Apuestas Abiertas"

    def cerrar_apuestas(self):
        self.betting_open = False
        self.save_state()
        return True, "Apuestas Cerradas"

    def _get_sorted_finalists(self):
        probs = self._calcular_probabilidades_final()
        if not probs: return []
        return sorted(probs.keys(), key=lambda p: probs[p], reverse=True)

    def _get_base_floor_for_candidate(self, candidate):
        ranked_finalists = self._get_sorted_finalists()
        if candidate not in ranked_finalists: return 2.0
        rank_idx = ranked_finalists.index(candidate)
        return CONSTANTS['FLOORS_BY_RANK_BASE'].get(rank_idx, 2.0)

    def _calculate_dynamic_floors(self, extra_bets=None):
        counts = defaultdict(int)
        for b in self.bets:
            counts[b['candidato']] += 1
        if extra_bets:
            for cand, qty in extra_bets.items():
                counts[cand] += qty
        base_floors = {p: self._get_base_floor_for_candidate(p) for p in self.final_table}
        current_floors = base_floors.copy()
        pressure_points = defaultdict(float)
        for p in self.final_table:
             n = counts[p]
             if n > 1:
                 drop = (n - 1) * 0.1
                 max_drop = base_floors[p] - CONSTANTS['PAYOUT_GLOBAL_FLOOR']
                 real_drop = min(drop, max_drop)
                 current_floors[p] -= real_drop
                 theoretical_pressure = (n - 1) * 0.1
                 pressure_points[p] = theoretical_pressure
        total_pressure = sum(pressure_points.values())
        num_candidates = len(self.final_table)
        if total_pressure > 0:
            if num_candidates > 1:
                for p in self.final_table:
                    pressure_from_others = total_pressure - pressure_points[p]
                    bonus_share = pressure_from_others / (num_candidates - 1)
                    current_floors[p] += bonus_share
                    current_floors[p] = max(CONSTANTS['PAYOUT_GLOBAL_FLOOR'], min(current_floors[p], CONSTANTS['PAYOUT_MAX_CAP']))
        return current_floors

    def _redondear_pago(self, monto):
        entero = int(monto)
        resto = entero % 100
        base = (entero // 100) * 100
        if resto > 50: return base + 100
        else: return base

    def validar_apuesta(self, candidato, monto):
        dynamic_floors = self._calculate_dynamic_floors(extra_bets={candidato: 1})
        floor = dynamic_floors.get(candidato, 1.5)
        current_bets_on_cand = sum(b['monto'] for b in self.bets if b['candidato'] == candidato)
        current_total_pool = sum(b['monto'] for b in self.bets)
        new_total_pool = current_total_pool + monto
        new_bets_on_cand = current_bets_on_cand + monto
        net_pool = new_total_pool * 0.90
        liability = new_bets_on_cand * floor
        solvency_capacity = net_pool + self.house_bankroll
        if liability > solvency_capacity:
            return False, f"🚫 **Apuesta Rechazada:** El riesgo supera la capacidad de la banca (Piso Dinámico: x{floor:.2f})."
        return True, "OK"

    def registrar_apuesta(self, apostador, candidato, monto):
        if not self.betting_open: return False, "Apuestas cerradas."
        if self.final_results: return False, "🚫 No se aceptan apuestas: La final ya tiene resultado."
        nombre_limpio = apostador.replace(" (Ext)", "").strip().upper()
        candidato_limpio = candidato.strip().upper()
        if nombre_limpio == candidato_limpio:
             return False, "🚫 Regla de Ética: Los finalistas no pueden apostar por sí mismos."
        if monto not in CONSTANTS['BET_AMOUNTS']: return False, "Monto inválido."
        if candidato not in self.final_table: return False, "Candidato no es finalista."
        for b in self.bets:
            if b['apostador'].strip().lower() == apostador.strip().lower():
                return False, f"Error: {apostador} ya tiene una apuesta registrada. Elimínala primero si deseas cambiarla."
        is_safe, msg = self.validar_apuesta(candidato, float(monto))
        if not is_safe: return False, msg
        self.bets.append({
            'apostador': apostador.strip(),
            'candidato': candidato,
            'monto': float(monto),
            'timestamp': time.time()
        })
        self.save_state()
        return True, f"Apuesta registrada: {apostador} -> {candidato} (${monto:,.0f})"

    def eliminar_apuesta(self, index):
        if not self.betting_open: return False, "No se pueden eliminar apuestas cuando están cerradas."
        if 0 <= index < len(self.bets):
            deleted = self.bets.pop(index)
            self.save_state()
            return True, f"Apuesta de {deleted['apostador']} eliminada."
        return False, "Índice inválido."

    def _calcular_probabilidades_final(self):
        if not self.final_table: return {}
        ranking = self._obtener_ranking_data()
        stats = {d['Jugador']: d for d in ranking if d['Jugador'] in self.final_table}
        scores = {}
        for p in self.final_table:
            d = stats.get(p, {})
            pv = d.get('PV', 0) * 50
            pm = d.get('PM', 0) * 2
            v = d.get('%V', 0) * 0.5
            scores[p] = pv + pm + v
        total_score = sum(scores.values())
        probs = {p: (s/total_score*100) if total_score else 0 for p, s in scores.items()}
        return probs

    def calcular_odds_tote_wrapper(self):
        total_pool = sum(b['monto'] for b in self.bets)
        net_pool = total_pool * 0.90
        bets_per_cand = defaultdict(float)
        counts_per_cand = defaultdict(int)
        for b in self.bets:
            bets_per_cand[b['candidato']] += b['monto']
            counts_per_cand[b['candidato']] += 1
        betting_favorite = None
        if bets_per_cand:
            betting_favorite = max(bets_per_cand, key=bets_per_cand.get)
        dynamic_floors = self._calculate_dynamic_floors()
        odds = {}
        for p in self.final_table:
            money_on_p = bets_per_cand[p]
            count_on_p = counts_per_cand[p]
            floor_dyn = dynamic_floors.get(p, 1.5)
            if money_on_p > 0:
                if count_on_p <= 1:
                    odds[p] = floor_dyn
                else:
                    raw_payout = net_pool / money_on_p
                    if raw_payout >= floor_dyn:
                         odds[p] = min(raw_payout, CONSTANTS['PAYOUT_MAX_CAP'])
                    else:
                         odds[p] = max(raw_payout, 1.0)
            else:
                odds[p] = floor_dyn
        return total_pool, odds, counts_per_cand, bets_per_cand, betting_favorite, dynamic_floors

    def simular_pago(self, candidato, monto_simulado):
        if not candidato or monto_simulado <= 0: return None
        current_total_pool = sum(b['monto'] for b in self.bets)
        current_count_on_cand = sum(1 for b in self.bets if b['candidato'] == candidato)
        simulated_floors = self._calculate_dynamic_floors(extra_bets={candidato: 1})
        floor_dyn = simulated_floors.get(candidato, 1.5)
        new_total_pool = current_total_pool + monto_simulado
        bets_on_cand_simulated = sum(b['monto'] for b in self.bets if b['candidato'] == candidato) + monto_simulado
        new_count_on_cand = current_count_on_cand + 1
        distributable = new_total_pool * 0.90
        raw_dividend = distributable / bets_on_cand_simulated
        if new_count_on_cand <= 1:
             final_dividend = floor_dyn
        else:
             if raw_dividend >= floor_dyn:
                 final_dividend = min(raw_dividend, CONSTANTS['PAYOUT_MAX_CAP'])
             else:
                 final_dividend = max(raw_dividend, 1.0)
        raw_win_amount = monto_simulado * final_dividend
        rounded_win_amount = self._redondear_pago(raw_win_amount)
        is_below_floor = final_dividend < floor_dyn and new_count_on_cand > 1
        is_capped = final_dividend == CONSTANTS['PAYOUT_MAX_CAP']
        return {
            'total_pool': new_total_pool,
            'dividend': final_dividend,
            'win_amount': rounded_win_amount,
            'is_below_floor': is_below_floor,
            'is_capped': is_capped,
            'floor_ref': floor_dyn
        }

    def _liquidar_apuestas(self, winner):
        if not self.bets: return
        total_pool = sum(b['monto'] for b in self.bets)
        bets_on_winner = [b for b in self.bets if b['candidato'] == winner]
        total_bet_winner = sum(b['monto'] for b in bets_on_winner)
        count_bet_winner = len(bets_on_winner)
        final_floors = self._calculate_dynamic_floors()
        floor_dyn = final_floors.get(winner, 1.5)
        results_log = []
        if total_bet_winner == 0:
            results_log.append("NADIE acertó al ganador. La Casa se lleva todo el pozo.")
            house_net_profit = total_pool
        else:
            distributable_pool = total_pool * 0.90
            raw_dividend = distributable_pool / total_bet_winner
            if count_bet_winner <= 1:
                final_dividend = floor_dyn
            else:
                if raw_dividend >= floor_dyn:
                    final_dividend = min(raw_dividend, CONSTANTS['PAYOUT_MAX_CAP'])
                else:
                    final_dividend = max(raw_dividend, 1.0)
            total_payout_real = 0
            payouts_info = []
            for b in bets_on_winner:
                raw_payout = b['monto'] * final_dividend
                final_payout = self._redondear_pago(raw_payout)
                profit = final_payout - b['monto']
                total_payout_real += final_payout
                payouts_info.append(f"✅ {b['apostador']} apostó ${b['monto']:.0f} -> Cobra ${final_payout:,.0f} (+${profit:,.0f})")
            house_net_profit = total_pool - total_payout_real
            results_log.append(f"💰 POZO TOTAL: ${total_pool:,.0f}")
            results_log.append(f"🏆 GANADOR: {winner}")
            results_log.append(f"📊 Factor de Pago Real: x{final_dividend:.2f} (Piso Dinámico: x{floor_dyn:.2f})")
            if house_net_profit < 0:
                 results_log.append(f"📉 La Casa cubrió pérdidas por ${abs(house_net_profit):,.0f} (Usando Banca/Comisión)")
            else:
                 results_log.append(f"🏦 Ganancia Neta Casa: ${house_net_profit:,.0f}")
            results_log.extend(payouts_info)
        self.house_bankroll += house_net_profit
        self.betting_results_log = results_log

# ==============================================================================
# 3. INTERFAZ DE USUARIO Y UTILIDADES (FRONTEND)
# Explicación: Configuración de página, estilos CSS, temporizador JavaScript y componentes comunes.
# ==============================================================================

st.set_page_config(page_title="Gestor Torneos Catan", layout="wide", page_icon="🎲")

def get_timer_html(target_timestamp=None, paused_seconds=None, is_big=False, is_floating=False):
    font_size = "300px" if is_big else "40px"
    align = "center" if is_big else "left"
    padding = "10px 30px" if is_big else "5px 15px"

    floating_js = ""
    if is_floating:
        floating_js = """
        <script>
        var f = window.frameElement;
        if (f) {
            f.style.position = 'fixed';
            f.style.top = '15px';
            f.style.right = '15px';
            f.style.width = '240px';
            f.style.height = '100px';
            f.style.zIndex = '999999';
            f.style.border = 'none';
        }
        </script>
        """

    if paused_seconds is not None:
        m = int(paused_seconds // 60)
        s = int(paused_seconds % 60)
        time_str = f"{m:02d}:{s:02d}"
        color = "#ffc107"
        text_extra = "<div style='font-size: 30px; color: gray; margin-top: -10px;'>⏸ PAUSADO</div>" if is_big else ""
        return f"""
        {floating_js}
        <div style="text-align: {align}; font-family: monospace; font-weight: bold; margin-bottom: 10px;">
            <div style="font-size: {font_size}; color: #333; background: #fff3cd; border: 4px solid {color}; padding: {padding}; border-radius: 20px; display: inline-block;">
                {time_str}
            </div>
            {text_extra}
        </div>
        """

    if target_timestamp is None: return "<div></div>"
    container_style = f"text-align: {align}; font-family: monospace; font-weight: bold; margin-bottom: 10px;"
    return f"""
    {floating_js}
    <div id="timer-container" style="{container_style}">
        <div id="timer-display" style="font-size: {font_size}; color: #333; background: #f0f2f6; padding: {padding}; border-radius: 20px; display: inline-block;">
            --:--
        </div>
    </div>
    <audio id="alarm-sound" src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" preload="auto"></audio>
    <script>
    (function() {{
        var target = {target_timestamp};
        var display = document.getElementById("timer-display");
        var audio = document.getElementById("alarm-sound");
        var played = false;
        function update() {{
            var now = new Date().getTime() / 1000;
            var diff = target - now;
            if (diff <= 0) {{
                display.innerHTML = "00:00";
                display.style.color = "white";
                display.style.backgroundColor = "#dc3545";
                display.innerHTML = "¡TIEMPO!";
                if (!played) {{ audio.play().catch(e => console.log("Audio req interact")); played = true; }}
                return;
            }}
            var m = Math.floor(diff / 60);
            var s = Math.floor(diff % 60);
            var mStr = m < 10 ? "0" + m : m;
            var sStr = s < 10 ? "0" + s : s;
            display.innerHTML = mStr + ":" + sStr;
            if (diff <= 300) {{
                display.style.color = "#dc3545";
                display.style.border = "6px solid #dc3545";
            }} else {{
                display.style.color = "#333";
                display.style.border = "none";
            }}
        }}
        var timerInterval = setInterval(update, 1000);
        update();
    }})();
    </script>
    """

st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px; text-align: center;}
    .big-font {font-size: 20px !important; font-weight: bold;}
    .winner {color: green; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

if 'manager' not in st.session_state:
    st.session_state.manager = TorneoManager()
    ok, msg = st.session_state.manager.load_state()
    if ok: st.toast(f"📥 {msg}", icon="💾")

if 'timer_end' not in st.session_state: st.session_state.timer_end = None
if 'timer_paused_left' not in st.session_state: st.session_state.timer_paused_left = None

tm = st.session_state.manager

# ==============================================================================
# 4. BARRA LATERAL (NAVEGACIÓN Y CONTROLES GLOBALES)
# Explicación: Menú principal, inyección de temporizador flotante y reproductor de música.
# ==============================================================================

with st.sidebar:
    st.title("🎲 Catan Manager")

    if st.session_state.timer_end:
        components.html(get_timer_html(target_timestamp=st.session_state.timer_end, is_big=False, is_floating=True), height=10)
    elif st.session_state.timer_paused_left is not None:
        components.html(get_timer_html(paused_seconds=st.session_state.timer_paused_left, is_big=False, is_floating=True), height=10)

    menu = st.radio(
        "Navegación",
        ["Inicio", "Jugadores", "Rondas & Mesas", "Resultados", "Clasificación",
         "Fases Finales", "Apuestas", "Exportar", "Temporizador", "Sorteo", "Generador de Mapas"]
    )
    st.divider()

    st.markdown("### 📂 Cargar Torneo")
    try:
        archivos_drive = [f for f in os.listdir(CARPETA_TORNEOS) if f.endswith(".json")]
        archivos_drive.sort(reverse=True)
    except Exception:
        archivos_drive = []
    else:
        st.caption("No se encontraron archivos en Drive.")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Guardar"):
            if tm.save_state(): st.success("Guardado")
            else: st.error("Error")
    with c2:
        if os.path.exists(CONSTANTS['AUTOSAVE_FILE']):
            with open(CONSTANTS['AUTOSAVE_FILE'], "r") as f:
                st.download_button(label="⬇️ Bajar Backup", data=f, file_name="respaldo_emergencia_catan.json", mime="application/json")
        else:
            st.warning("Sin datos")

    st.divider()
    st.caption(f"Jugadores: {len(st.session_state.manager.players)}")
    st.caption(f"Fase: {str(tm.phase).upper()}")
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; font-size: 12px; color: gray;'>
    <b>© 2025 Sistema APP Manager Chile </b><br><br>
    <b>Propiedad Intelectual:</b><br>
    Este software (App Manager Chile), incluyendo su código fuente, diseño lógico y algoritmos, es obra original de <b>Simón Carvajal B.</b> y está protegido por las leyes de propiedad intelectual.<br><br>
    <b>Aviso Legal Catan®:</b><br>
    Catan® es una marca registrada de Catan GmbH y Catan Studio. Todos los derechos de autor, marcas comerciales, logotipos, arte gráfico, mecánicas y componentes físicos del juego pertenecen de manera exclusiva a sus respectivos creadores y titulares legales (incluyendo a Catan GmbH, Catan Studio, Asmodee y Devir como distribuidor oficial). La realización de este torneo por parte de las Comunidades de Catán en Chile es una iniciativa estrictamente independiente, gestionada por la comunidad de jugadores. La organización declara explícitamente que no ejerce explotación comercial ni busca el lucro indebido sobre la propiedad intelectual de terceros. Cualquier valor monetario asociado a la participación (cuotas de inscripción) se recauda a título de fondo común y está destinado de manera íntegra y exclusiva a sufragar los costos operativos del evento, tales como logística, arriendo de recintos, gestión administrativa, alimentacion, transporte, materiales y la adquisición de premios para los competidores. La organización no reclama titularidad alguna sobre la marca Catan ni actúa como representante comercial de sus dueños.<br><br>
    <b>Aviso de Terceros:</b><br>
    La herramienta "Catan Board Generator" integrada en este sistema es propiedad intelectual exclusiva de <b>Jamison Bunge</b> (<a href="https://catan.bunge.io/" target="_blank" style="color: gray;">catan.bunge.io</a>).<br><br>
    <b>Licencia de Uso:</b><br>
    Este software gestor es de uso gratuito únicamente bajo la condición de citar correctamente a su autor y otorgar los créditos correspondientes. Cualquier otro uso, reproducción o modificación sin autorización expresa está prohibido.<br><br>
    <b>Créditos:</b><br>
    Desarrollo: Simón Carvajal B. <a href="https://www.instagram.com/catanuniversechile/" target="_blank" style="color: gray;"><b> Catan Universe Chile </b></a><br> <br>
    (<a href="mailto:simon.carvajal24@gmail.com" style="color: gray;">simon.carvajal24@gmail.com</a>)<br><br>
    Agradecimientos especiales a<br>
    <b>Odette Garrido</b>, Loreto Gacitua y <a href="https://www.instagram.com/lasecatadelcatan?igsh=MXV2bXRuNWNseG1tbQ==" target="_blank" style="color: gray;"><b>La Secata </b></a><br>
    por su colaboración.<br><br>
    <i>Santiago, Chile 2025. Todos los derechos reservados.</i>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 5. PÁGINAS DEL MENÚ
# Explicación: Cada opción del menú lateral renderiza una interfaz específica y acopla sus lógicas.
# ==============================================================================

# 5.1 PÁGINA INICIO
# Explicación: Renderiza la portada del sistema, configuraciones iniciales y el reglamento técnico actualizado con la regla de Ventaja Deportiva.
if menu == "Inicio":
    st.title("🏆 Gestor de Torneos")
    if not tm.tournament_name:
        st.warning("⚠️ Configuración Inicial Requerida")
        with st.container(border=True):
            st.markdown("### 📝 Nombre del Torneo")
            st.info("Para comenzar, ingresa un nombre para identificar este torneo. Se usará para guardar los respaldos.")
            t_name = st.text_input("Escribe el nombre aquí:", placeholder="Ej: Torneo Verano 2025")
            if st.button("Confirmar y Comenzar", type="primary"):
                if t_name.strip():
                    tm.tournament_name = t_name.strip()
                    tm.save_state()
                    st.rerun()
                else: st.error("El nombre no puede estar vacío.")
        st.stop()

    st.markdown(f"### 🚩 {tm.tournament_name}")
    st.markdown("""
    Bienvenido al sistema de gestión.
    **Pasos rápidos:**
    1. Ve a **Jugadores** para cargar tu Excel o agregar manualmente.
    2. Ve a **Rondas** para configurar y generar el fixture.
    3. Usa **Resultados** para ingresar los puntos mesa a mesa.
    4. Revisa **Clasificación** para ver el ranking en tiempo real.
    5. Para ver el reglamento del torneo [**Haz click aqui.**](https://drive.google.com/file/d/1bRV4HeV1hZSghXM0YioSU0MN_cKtfie2/view?usp=sharing)
    """)
    if st.button("🔴 Reiniciar Torneo Completo"):
        if os.path.exists(CONSTANTS['AUTOSAVE_FILE']):
            os.remove(CONSTANTS['AUTOSAVE_FILE'])
        st.session_state.manager = TorneoManager()
        st.rerun()

    st.divider()
    st.subheader("📜 Criterios Técnicos")
    with st.container(border=True):
        st.markdown("""
### 📊 Criterios de Clasificación
El orden de prioridad en la **Tabla de Posiciones** es:
1. **Estatus** (Activo > Retirado)
2. **Puntos de Victoria (PV)**
3. **Puntos de Mesa (PM)**
4. **Rendimiento (%V)**
5. **Cantidad de 2dos / 3ros lugares**

---
### 🧮 Definiciones de Puntaje
#### 1. Puntos de Victoria (PV)
Se otorgan según la posición obtenida en la mesa:
* 🥇 **Ganador único:** 1.0 PV
* 🤝 **Empate (2 jugadores):** 0.5 PV c/u
* 🤝 **Empate (3 jugadores):** 0.33 PV c/u
* 🤝 **Empate (4 jugadores):** 0.25 PV c/u
#### 2. Rendimiento (%V) y Mesas de 3
Es el porcentaje de puntos que obtuvo el jugador respecto al total de puntos disponibles en la mesa.
* **Fórmula:** `(Mis Puntos / Total Puntos Mesa) * 100`
* **⚖️ Ajuste Mesas de 3 Jugadores:** En mesas de 3 hay "menos puntos" totales, lo que inflaría artificialmente el %V. Para evitar esta ventaja injusta frente a las mesas de 4, el sistema **agrega un "4to jugador virtual"** al denominador, sumando el promedio de puntos de esa mesa. Así, un 10 en mesa de 3 vale lo mismo que un 10 en mesa de 4.
#### 3. Puntos de Mesa (PM)
Es la suma simple de los puntos obtenidos en el tablero (Ej: 10, 8, 6...).

---
### 📏 Posiciones en Mesa (Ranking Denso)
El sistema utiliza **Ranking Denso** para definir los lugares dentro de una mesa en caso de empates.
* Si dos jugadores empatan en el 2do lugar, ambos reciben el puesto 2.
* El siguiente jugador recibe el puesto **3** (no se salta al 4).
* *Ejemplo:* 1ro (10pts), 2do (9pts), 2do (9pts), 3ro (7pts).

---
### 🎯 Ventaja Deportiva en Mesa (Elección de Turno, Asiento y Color)
En las fases de Semifinal y Final, el sistema aplica ventaja deportiva estricta basada en el rendimiento previo:
* **Orden de Prioridad:** El jugador con la mejor posición (Seed más bajo) en la Tabla General de Clasificación tiene el derecho a ser el primero en elegir:
    1. El **turno inicial** en el que desea jugar (1°, 2°, 3° o 4°).
    2. Su **asiento físico** en la mesa.
    3. El **color de sus piezas**.
* Este proceso de selección se repite sucesivamente con el 2do, 3ro y 4to jugador de la mesa en orden estricto de su posición en la tabla de clasificación. El último jugador en elegir deberá quedarse con la opción de turno, asiento y color restante.

---
### 🏆 Estructura de Fases Finales (Automático)
El sistema sugiere el formato según la asistencia:
* **12 a 28 Jugadores:** 🏁 **Final Directa** (Top 4 pasan a la Mesa Final).
* **29 o más Jugadores:** ⚔️ **Semifinales** (Top 16 juegan semis -> Ganadores a Final).
*(Nota: Con menos de 12 jugadores también se genera Final Directa, pero se recomienda usar los botones de "Forzar" en la pestaña Fases Finales según convenga).*

---
### 🎲 Sistemas de Emparejamiento
* **Sistema Aleatorio:**
    * *Recomendado para:* **Menos de 12 jugadores**.
    * *Lógica:* Intenta que no se repitan rivales y mezcla equipos.
* **Sistema Suizo:**
    * *Recomendado para:* **12 o más jugadores**.
    * *Lógica:* Empareja "Fuerte vs Fuerte" basándose en el ranking actual. Evita desequilibrios y define mejor el Top 4.

---
### ⚔️ Desempate en Finales
1. Se decide primero por **Puntos en la Partida (PM)**.
2. Si hay empate en puntos, gana automáticamente el jugador que tenía **mejor Ranking General (Seed)** antes de entrar a la mesa *(Ventaja Deportiva)*.

---
### 🔄 Reglas de Reemplazo (Ante abandono)
* **En Semifinales:** Entra el siguiente mejor jugador disponible de la Tabla General.
* **En la Gran Final:**
    * *Si hubo Semis:* Entra el **2do lugar** de la misma mesa de semifinal de donde vino el que abandonó (Desempate por Ranking de Tabla si aplica).
    * *Si fue Final Directa:* Entra el siguiente disponible de la Tabla General.
""")

# ==============================================================================
# 5.2 PÁGINA: JUGADORES
# Responsabilidad: Permite agregar, editar, eliminar jugadores y cargar desde Excel con filtrado, orden alfabético y control de duplicados.
# ==============================================================================
elif menu == "Jugadores":
    st.header("👥 Gestión de Jugadores")
    tab1, tab2 = st.tabs(["Agregar Manual", "Cargar Excel"])
    with tab1:
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: name: str = st.text_input("Nombre")
        with c2: team: str = st.text_input("Equipo (Opcional)")
        with c3:
            st.write("")
            if st.button("Agregar", use_container_width=True):
                ok, msg = tm.agregar_jugador(name, team)
                if ok: st.success(msg)
                else: st.error(msg)
    with tab2:
        uploaded = st.file_uploader("Subir Excel (.xlsx)", type=['xlsx'])
        if uploaded:
            if st.button("Procesar Archivo"):
                try:
                    df = pd.read_excel(uploaded)
                    ok, msg = tm.cargar_desde_dataframe(df)
                    if ok: st.success(msg)
                    else: st.error(msg)
                except Exception as e:
                    st.error(f"Error procesando Excel: {e}")

    # ==============================================================================
    # 5.2.1 Interfaz de Visualización, Búsqueda y Eliminación de Jugadores
    # Responsabilidad: Renderizar la lista reactiva de jugadores ordenados alfabéticamente con control de excepciones, aplicar filtro de búsqueda y manejar eliminación global.
    # ==============================================================================
    st.divider()
    c_head, c_search, c_del = st.columns([2, 2, 1])
    with c_head:
        st.subheader("Lista de Inscritos")
    with c_search:
        busqueda: str = st.text_input("🔍 Buscar jugador...", placeholder="Escribe un nombre...")
    with c_del:
        st.write("")
        with st.popover("🗑️ Vaciar Lista", use_container_width=True):
            st.markdown("¿Eliminar **TODOS** los jugadores?")
            if st.button("Confirmar Eliminación", type="primary"):
                try:
                    ok, msg = tm.eliminar_todos_los_jugadores()
                    if ok:
                        st.success(msg)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)
                except Exception as e:
                    st.error(f"Excepción UI al eliminar: {str(e)}")

    if tm.players:
        try:
            # Filtrado condicional según la búsqueda
            jugadores_base: list[dict] = [p for p in tm.players if busqueda.lower() in str(p.get('name', '')).lower()] if busqueda else list(tm.players)

            # Ordenamiento alfabético estricto por nombre
            jugadores_filtrados: list[dict] = sorted(jugadores_base, key=lambda x: str(x.get('name', '')).lower())

            if not jugadores_filtrados:
                st.info("No se encontraron jugadores con ese criterio de búsqueda.")
            else:
                for i, p in enumerate(jugadores_filtrados, 1):
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([0.5, 3, 1])
                        c1.write(f"**#{i}**")
                        info_text: str = f"**{p.get('name', '')}**"
                        if p.get('team', ''):
                            info_text += f" _({p['team']})_"
                        c2.markdown(info_text)

                        with c3:
                            col_edit, col_del = st.columns(2)
                            with col_edit:
                                with st.popover("✏️"):
                                    st.markdown(f"Editar **{p['name']}**")
                                    new_n: str = st.text_input("Nombre", value=p['name'], key=f"ed_n_{p['name']}")
                                    new_t: str = st.text_input("Equipo", value=p['team'], key=f"ed_t_{p['name']}")
                                    if st.button("Guardar", key=f"save_{p['name']}"):
                                        ok, msg = tm.editar_jugador(p['name'], new_n, new_t)
                                        if ok:
                                            st.success("Guardado")
                                            time.sleep(0.5)
                                            st.rerun()
                                        else:
                                            st.error(msg)
                            with col_del:
                                if st.button("🗑️", key=f"del_{p['name']}"):
                                    ok, msg = tm.eliminar_jugador(p['name'])
                                    if ok:
                                        st.success(msg)
                                    time.sleep(0.7)
                                    st.rerun()

            if tm.player_count_changes_log:
                st.info("⚠️ Novedades recientes: " + " | ".join(tm.player_count_changes_log[-3:]))
        except Exception as e:
            st.error(f"Error al procesar la lista de jugadores: {str(e)}")
    else:
        st.info("No hay jugadores inscritos.")

# ==============================================================================
# 5.3 PÁGINA: RONDAS Y MESAS
# Explicación: Generación de rondas y visualización de mesas con inyección dinámica de la imagen del mapa general de la ronda.
# ==============================================================================
elif menu == "Rondas & Mesas":
    st.header("⚔️ Generador de Rondas")
    c1, c2, c3 = st.columns(3)
    with c1: num_rondas = st.number_input("Cantidad Rondas", 2, 4, 3)
    with c2: tipo = st.selectbox("Tipo", ["aleatorio", "suizo", "aleatorio_p16"], format_func=lambda x: "Aleatorio P16" if x == "aleatorio_p16" else x.capitalize())

    n_players = len(tm.players)
    if n_players >= CONSTANTS['MIN_PLAYERS']:
        with st.expander("💡 Análisis de Viabilidad y Sugerencias", expanded=True):
            m4, m3 = 0, 0
            rem = n_players % 4
            if rem == 0: m4 = n_players // 4
            elif rem == 1: m4 = (n_players - 9) // 4; m3 = 3
            elif rem == 2: m4 = (n_players - 6) // 4; m3 = 2
            elif rem == 3: m4 = n_players // 4; m3 = 1
            total_mesas = m4 + m3
            st.markdown("---")
            st.markdown("**🧠 Recomendación de Sistema:**")
            if tipo == "aleatorio_p16":
                st.info("ℹ️ **Sistema Aleatorio P16:** Exclusivo para 16+ jugadores. Intenta garantizar que cada jugador pase por la 1ra, 2da, 3ra y 4ta posición en sus mesas a lo largo de 4 rondas sin repetir rivales.")
            elif n_players >= 12:
                if tipo == "aleatorio":
                    st.warning("""
                    ⚠️ **Sugerencia:** Tienes **más de 12 jugadores**.
                    El sistema **Aleatorio** puede generar mesas desequilibradas (Expertos vs Novatos) en rondas avanzadas.
                    👉 Se recomienda cambiar a **Sistema Suizo** para que los jugadores con puntaje similar jueguen entre sí.
                    """)
                else: st.success("✅ **Elección Correcta:** El **Sistema Suizo** es ideal para grupos grandes (+12).")
            else:
                if tipo == "suizo":
                    st.info("""
                    ℹ️ **Nota:** Con **pocos jugadores (-12)**, el sistema Suizo puede forzar repetición de rivales muy rápido.
                    👉 El sistema **Aleatorio** suele funcionar mejor para grupos pequeños.
                    """)
                else: st.success("✅ **Elección Correcta:** El sistema **Aleatorio** es ideal para grupos pequeños.")

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.markdown("**1️⃣ Distribución de Mesas:**")
                if total_mesas == 0: st.error("⚠️ Error: Insuficientes jugadores.")
                elif m3 == 0: st.success(f"✅ Perfecta: {m4} mesas de 4.")
                else: st.warning(f"⚠️ Irregular: {m4} de 4 y **{m3} de 3**.")
            with col_b:
                st.markdown("**2️⃣ Choque de Equipos:**")
                equipos_count = {}
                for p in tm.players:
                    t = p.get('team', '')
                    if t: equipos_count[t] = equipos_count.get(t, 0) + 1
                if equipos_count and total_mesas > 0:
                    max_team_size = max(equipos_count.values())
                    biggest_team = next(t for t, c in equipos_count.items() if c == max_team_size)
                    if max_team_size > total_mesas:
                        st.error(f"🛑 **Inevitable:** '{biggest_team}' tiene {max_team_size} jug. y solo hay {total_mesas} mesas.")
                    elif max_team_size == total_mesas:
                        st.warning(f"⚠️ **Al Límite:** '{biggest_team}' tiene {max_team_size} jug. Llenarán 1 cupo exacto por mesa.")
                    else:
                        st.success(f"✅ **Evitable:** Los equipos caben sin repetirse en las {total_mesas} mesas.")
                elif not equipos_count and total_mesas > 0:
                    st.success("✅ **Sin equipos:** Todos juegan individual.")
                else:
                    st.write("-")
            with col_c:
                st.markdown("**3️⃣ Repetición de Rivales:**")
                if n_players > 0:
                    max_rondas_ideal = (n_players - 1) // 3
                    if num_rondas <= max_rondas_ideal:
                        st.success(f"✅ **Viable:** {num_rondas} Rondas posibles sin repetir.")
                    elif num_rondas == max_rondas_ideal + 1:
                        st.warning(f"⚠️ **Riesgo Alto:** {num_rondas} rondas está al límite matemático.")
                    else:
                        st.error(f"🛑 **Segura:** A partir de ronda {max_rondas_ideal+1} se repetirán rivales.")
                else:
                    st.write("-")

    if len(tm.players) >= 12 and num_rondas > 3 and tipo == "aleatorio":
        st.warning("⚠️ Sugerencia: Tienes más de 12 jugadores y varias rondas. Se recomienda usar el **Sistema Suizo**.")

    with c3:
        st.write("")
        if st.button("Generar / Actualizar Fixture", type="primary"):
            ok, msg = tm.generar_rondas(num_rondas, tipo)
            if ok: st.success(msg)
            else: st.error(msg)

    st.divider()
    if tm.player_count_changes_log:
        st.info("⚠️ Novedades recientes: " + " | ".join(tm.player_count_changes_log[-3:]))

    if not tm.rounds:
        st.warning("No hay rondas generadas.")
    else:
        tabs = st.tabs([f"Ronda {i+1}" for i in range(len(tm.rounds))])
        for i, tab in enumerate(tabs):
            with tab:
                ronda = tm.rounds[i]
                status = "✅ JUGADA" if ronda['played'] else "⏳ PENDIENTE"
                st.markdown(f"**Estado:** {status} | **Tipo:** {ronda.get('type','?').upper()}")
                if not ronda['tables']: st.info("Mesas aún no generadas.")
                else:
                    cols = st.columns(3)
                    for idx, mesa in enumerate(ronda['tables']):
                        with cols[idx % 3]:
                            with st.container(border=True):
                                st.write(f"**Mesa {idx+1}**")
                                mkey = (i+1, idx+1)
                                if mkey in tm.results:
                                    res = tm.results[mkey]
                                    table_data = []
                                    for p in mesa:
                                        if p in res:
                                            d = res[p]
                                            table_data.append({"Pos": d['P°'], "Jugador": p, "PV": d['PV'], "PM": d['PM'], "%V": f"{d['%V']:.1f}%"})
                                        else:
                                            table_data.append({"Pos": "-", "Jugador": p, "PV": "-", "PM": "-", "%V": "-"})
                                    if table_data:
                                        table_data.sort(key=lambda x: x["Pos"] if isinstance(x["Pos"], int) else 99)
                                        st.dataframe(pd.DataFrame(table_data), hide_index=True)
                                else:
                                    for p in mesa:
                                        team = tm.player_teams.get(p,'')
                                        st.write(f"- {p} " + (f"({team})" if team else ""))
                    if not ronda['played']:
                        st.divider()
                        with st.expander("🛠️ Gestión Manual / Intercambiar Jugadores", expanded=False):
                            st.warning("⚠️ Forzar cambios ignorará las reglas de equipos, rivales y posiciones.")
                            c_swap1, c_swap_icon, c_swap2 = st.columns([2, 0.5, 2])
                            mesas_idxs = list(range(1, len(ronda['tables']) + 1))
                            with c_swap1:
                                m1_sel = st.selectbox("Mesa Origen", mesas_idxs, key=f"m1_r{i}")
                                players_m1 = ronda['tables'][m1_sel-1]
                                p1_sel = st.selectbox("Jugador 1", players_m1, key=f"p1_r{i}")
                            with c_swap_icon:
                                st.markdown("<br><br><div style='text-align: center; font-size: 24px;'>↔️</div>", unsafe_allow_html=True)
                            with c_swap2:
                                m2_sel = st.selectbox("Mesa Destino", mesas_idxs, index=min(1, len(mesas_idxs)-1), key=f"m2_r{i}")
                                players_m2 = ronda['tables'][m2_sel-1]
                                p2_sel = st.selectbox("Jugador 2", players_m2, key=f"p2_r{i}")
                            if st.button("Confirmar Intercambio", key=f"btn_swap_{i}"):
                                if m1_sel == m2_sel and p1_sel == p2_sel: st.error("Selecciona jugadores distintos.")
                                else:
                                    ok, msg = tm.intercambio_manual(i+1, m1_sel, p1_sel, m2_sel, p2_sel)
                                    if ok: st.success(msg); time.sleep(1); st.rerun()
                                    else: st.error(msg)

                    st.markdown("---")
                    st.markdown(f"### 📸 Exportar Fixture de la Ronda {i+1}")
                    st.caption("Genera una imagen consolidada de las mesas y el mapa oficial de la ronda para descargar.")

                    html_mesas = ""
                    for idx, mesa in enumerate(ronda['tables']):
                        html_mesas += f"<div class='mesa-card'><h4>Mesa {idx+1}</h4><ul>"
                        for p in mesa:
                            html_mesas += f"<li>{p}</li>"
                        html_mesas += "</ul></div>"

                    key_map = f"clasificatoria_{i+1}"
                    mapa_img = tm.maps.get(key_map, "")
                    html_mapa = f"<div style='text-align:center; margin-top: 20px;'><img src='{mapa_img}' style='max-width: 90%; border-radius: 8px; border: 2px solid #2c3e50;'/></div>" if mapa_img else ""

                    html_fixture = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
                        <style>
                            body {{ font-family: sans-serif; background-color: transparent; }}
                            #captura-ronda-{i} {{
                                background-color: white; padding: 20px; border-radius: 10px;
                                display: inline-block; width: 95%; box-sizing: border-box;
                            }}
                            .mesas-grid {{
                                display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; margin-top: 15px;
                            }}
                            .mesa-card {{
                                border: 2px solid #2c3e50; border-radius: 8px; padding: 10px;
                                min-width: 180px; flex: 1 1 200px; max-width: 250px;
                                background-color: #f8f9fa; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                                box-sizing: border-box;
                            }}
                            .mesa-card h4 {{
                                margin-top: 0; text-align: center; color: #ffffff; background-color: #2c3e50;
                                padding: 8px; border-radius: 5px 5px 0 0; margin: -10px -10px 10px -10px;
                            }}
                            .mesa-card ul {{ list-style-type: none; padding-left: 0; margin-bottom: 0; }}
                            .mesa-card li {{
                                padding: 6px 0; border-bottom: 1px dashed #cccccc;
                                text-align: center; font-weight: bold; color: #333333;
                            }}
                            .mesa-card li:last-child {{ border-bottom: none; }}
                            .export-btn {{
                                background-color: #ff4b4b; color: white; border: none; padding: 10px 20px;
                                font-size: 16px; cursor: pointer; border-radius: 8px; font-weight: bold; margin-bottom: 15px;
                            }}
                            .export-btn:hover {{ background-color: #ff3333; }}
                        </style>
                    </head>
                    <body>
                        <button class="export-btn" onclick="capturar()">📸 Copiar Imagen al Portapapeles</button>
                        <br>
                        <div id="captura-ronda-{i}">
                            <h2 style="text-align: center; color: #2c3e50; margin-bottom: 5px;">{tm.tournament_name}</h2>
                            <h4 style="text-align: center; color: #7f8c8d; margin-top: 0;">Fixture Oficial — Ronda {i+1}</h4>
                            <div class="mesas-grid">
                                {html_mesas}
                            </div>
                        </div>

                        <script>
                            function capturar() {{
                                var element = document.getElementById('captura-ronda-{i}');
                                html2canvas(element, {{ scale: 2, backgroundColor: '#ffffff' }}).then(function(canvas) {{
                                    canvas.toBlob(function(blob) {{
                                        if (typeof ClipboardItem !== 'undefined' && navigator.clipboard && navigator.clipboard.write) {{
                                            const item = new ClipboardItem({{"image/png": blob}});
                                            navigator.clipboard.write([item]).then(function() {{
                                                alert("✅ Imagen del Fixture copiada al portapapeles correctamente.");
                                            }}).catch(function() {{ descargar(canvas); }});
                                        }} else {{ descargar(canvas); }}
                                    }});
                                }});
                            }}
                            function descargar(canvas) {{
                                var link = document.createElement('a');
                                link.download = 'fixture_ronda_{i+1}_{tm.tournament_name.replace(" ", "_")}.png';
                                link.href = canvas.toDataURL('image/png');
                                link.click();
                                alert("📥 Imagen descargada.");
                            }}
                        </script>
                    </body>
                    </html>
                    """
                    iframe_height = 200 + (((len(ronda['tables']) - 1) // 3) + 1) * 250
                    components.html(html_fixture, height=iframe_height, scrolling=True)
        if tm.last_round_generation_msg:
            st.divider()
            if "✅" in tm.last_round_generation_msg: st.success(tm.last_round_generation_msg)
            else: st.warning(tm.last_round_generation_msg)

# ==============================================================================
# 5.4 PÁGINA: RESULTADOS (REGISTRO DE PUNTUACIONES POR MESA)
# Responsabilidad: Capturar, validar y persistir los puntos de mesa mediante manejo estricto de excepciones y tipado.
# ==============================================================================
elif menu == "Resultados":
    st.header("📝 Registro de Resultados por Mesa")
    try:
        if not tm.rounds:
            st.warning("No hay rondas generadas. Ve a 'Rondas & Mesas' y genera el fixture primero.")
            st.stop()

        rondas_disponibles: list[int] = [i + 1 for i, r in enumerate(tm.rounds)]
        ronda_sel: int = int(st.selectbox("Seleccionar Ronda", rondas_disponibles, format_func=lambda x: f"Ronda {x}"))
        ronda_idx: int = ronda_sel - 1
        ronda: dict = tm.rounds[ronda_idx]

        if not ronda.get('tables'):
            st.error(f"La Ronda {ronda_sel} no tiene mesas definidas. Regenera las rondas.")
            st.stop()

        if bool(ronda.get('played')):
            st.success(f"✅ La Ronda {ronda_sel} ya está completamente registrada.")
            for mesa_idx in range(1, len(ronda['tables']) + 1):
                mkey: tuple[int, int] = (ronda_sel, mesa_idx)
                if mkey in tm.results:
                    st.subheader(f"Mesa {mesa_idx}")
                    res: dict = tm.results[mkey]
                    data: list[dict] = []
                    for p, d in res.items():
                        data.append({
                            "Jugador": str(p),
                            "PM": float(d.get('PM', 0.0)),
                            "PV": float(d.get('PV', 0.0)),
                            "%V": f"{float(d.get('%V', 0.0)):.1f}%",
                            "Pos": int(d.get('P°', 0))
                        })
                    st.dataframe(pd.DataFrame(data), hide_index=True)
            st.info("Puedes editar un resultado volviendo a seleccionar la mesa y guardando nuevos valores (sobrescribirá).")

        else:
            mesas: list[int] = list(range(1, len(ronda['tables']) + 1))
            mesa_sel: int = int(st.selectbox("Seleccionar Mesa", mesas, format_func=lambda x: f"Mesa {x}"))
            mesa_idx_sel: int = mesa_sel - 1
            mesa_jugadores: list[str] = [str(jug) for jug in ronda['tables'][mesa_idx_sel]]

            st.markdown(f"### Mesa {mesa_sel} - Jugadores:")
            mkey_sel: tuple[int, int] = (ronda_sel, mesa_sel)
            valores_previos: dict[str, int] = {}

            if mkey_sel in tm.results:
                valores_previos = {str(p): int(tm.results[mkey_sel][p].get('PM', 2)) for p in mesa_jugadores}
                st.info("⚠️ Esta mesa ya tiene resultados guardados. Si guardas de nuevo, se sobrescribirán.")

            # ==============================================================================
            # 5.4.1 Inyección de Puntaje y Atajos UI
            # Responsabilidad: Formulario de captura de puntos con tipado seguro y callback reactivo.
            # ==============================================================================
            def set_score_10_clasif(key_input: str) -> None:
                try:
                    st.session_state[key_input] = 10
                except Exception as exc:
                    st.error(f"Error al establecer puntaje: {str(exc)}")

            with st.form(key=f"resultados_r{ronda_sel}_m{mesa_sel}"):
                scores: dict[str, int] = {}
                cols = st.columns(min(len(mesa_jugadores), 4))

                for i, jugador in enumerate(mesa_jugadores):
                    with cols[i % 4]:
                        st.write(f"**{jugador}**")
                        try:
                            valor_default: int = int(valores_previos.get(jugador, 2))
                        except (ValueError, TypeError):
                            valor_default = 2

                        key_pm: str = f"pm_{ronda_sel}_{mesa_sel}_{jugador}"

                        if key_pm not in st.session_state:
                            st.session_state[key_pm] = valor_default

                        c_in, c_btn = st.columns([3, 1])
                        with c_in:
                            pm = st.number_input("PM", min_value=int(CONSTANTS['MIN_PM']), max_value=int(CONSTANTS['MAX_PM']), key=key_pm, label_visibility="collapsed")
                        with c_btn:
                            st.form_submit_button("10", on_click=set_score_10_clasif, args=(key_pm,), use_container_width=True, key=f"btn_10_clasif_{key_pm}")

                        scores[str(jugador)] = int(pm)

                opciones_ganador: list[str] = ["Automático (por puntos)"] + mesa_jugadores
                ganador_manual: str = str(st.selectbox(
                    "Ganador manual (opcional - solo si quieres forzar un campeón de mesa)",
                    opciones_ganador,
                    key=f"winner_{ronda_sel}_{mesa_sel}"
                ))
                winner_value: str | None = None if ganador_manual == "Automático (por puntos)" else ganador_manual

                submitted: bool = st.form_submit_button("Guardar Resultado de esta Mesa", type="primary")

            if submitted:
                ok, msg = tm.registrar_resultados(ronda_sel, mesa_sel, scores, winner_value)
                if ok:
                    st.success(f"✅ {msg}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Error: {msg}")

        st.divider()
        st.subheader("Progreso de la Ronda Actual")
        try:
            mesas_totales_calc = len(ronda.get('tables', []))
            ronda_int = int(ronda_sel)

            # Casteo explícito de tipos para validación cruzada segura
            mesas_registradas_set = set(t for r, t in tm.results.keys() if r == ronda_int)
            mesas_completadas_calc = len(mesas_registradas_set)

            # Diferencia de conjuntos para obtener las faltantes
            mesas_faltantes_list = [t for t in range(1, mesas_totales_calc + 1) if t not in mesas_registradas_set]

            progreso_flt = float(mesas_completadas_calc / mesas_totales_calc) if mesas_totales_calc > 0 else 0.0

            st.progress(progreso_flt)
            st.caption(f"Mesas registradas: {mesas_completadas_calc} de {mesas_totales_calc}")

            if mesas_faltantes_list:
                st.warning(f"⚠️ Faltan resultados para las mesas: {', '.join(map(str, mesas_faltantes_list))}")

            if mesas_completadas_calc == mesas_totales_calc and mesas_totales_calc > 0 and not bool(ronda.get('played')):
                st.info("🎉 ¡Todas las mesas de esta ronda están registradas! El sistema marcará la ronda como jugada automáticamente.")

        except Exception as error_progreso:
            st.error(f"Error interno al calcular el progreso: {str(error_progreso)}")

    except Exception as e:
        st.error(f"Error crítico procesando la interfaz de Resultados: {str(e)}")

# ==============================================================================
# 5.5 PÁGINA: CLASIFICACIÓN
# Explicación: Despliega el ranking del torneo e integra la fecha actual dinámicamente en la exportación de imágenes.
# ==============================================================================
elif menu == "Clasificación":
    import pandas as pd
    import streamlit.components.v1 as components
    from datetime import datetime
    st.header("📊 Tabla de Posiciones")
    data = tm._obtener_ranking_data()
    if data:
        df = pd.DataFrame(data)
        df['Activo'] = df['Activo'].apply(lambda x: "Sí" if x == 1 else "No")
        df.insert(0, 'Pos', range(1, 1 + len(df)))
        columnas_predeterminadas = [col for col in df.columns if col != 'Equipo']
        st.dataframe(df, use_container_width=True, hide_index=True, column_order=columnas_predeterminadas)
        st.markdown("---")
        st.markdown("### 📸 Exportar Tabla Completa")
        st.caption("Usa el botón para copiar la imagen al portapapeles (o descargarla si tu navegador lo bloquea). También puedes seleccionar el texto manualmente.")
        fecha_actual = datetime.now().strftime("%d/%m/%Y")
        df_imagen = df.drop(columns=['Equipo'])
        html_table = df_imagen.to_html(index=False, border=0, classes="styled-table", justify="center")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
            <style>
                body {{ font-family: sans-serif; background-color: transparent; }}
                #contenedor-tabla-captura {{
                    background-color: white; padding: 20px; border-radius: 10px;
                    display: inline-block; width: 95%;
                }}
                .styled-table {{ border-collapse: collapse; margin: 10px 0; font-size: 14px; width: 100%; box-shadow: 0 0 15px rgba(0, 0, 0, 0.1); }}
                .styled-table thead tr {{ background-color: #2c3e50; color: #ffffff; text-align: center; }}
                .styled-table th, .styled-table td {{ padding: 12px 15px; text-align: center; border: 1px solid #dddddd; }}
                .styled-table tbody tr {{ border-bottom: 1px solid #dddddd; }}
                .styled-table tbody tr:nth-of-type(even) {{ background-color: #f8f9fa; }}
                .styled-table tbody tr:last-of-type {{ border-bottom: 2px solid #2c3e50; }}
                .export-btn {{
                    background-color: #ff4b4b; color: white; border: none; padding: 10px 20px;
                    font-size: 16px; cursor: pointer; border-radius: 8px; font-weight: bold; margin-bottom: 15px;
                }}
                .export-btn:hover {{ background-color: #ff3333; }}
            </style>
        </head>
        <body>
            <button class="export-btn" onclick="capturar()">📸 Copiar Imagen al Portapapeles</button>
            <br>
            <div id="contenedor-tabla-captura">
                <h2 style="text-align: center; color: #2c3e50; margin-bottom: 5px;">{tm.tournament_name}</h2>
                <h4 style="text-align: center; color: #7f8c8d; margin-top: 0;">Tabla de Posiciones Catan Challenger Chile — {fecha_actual}</h4>
                {html_table}
            </div>
            <script>
                function capturar() {{
                    var element = document.getElementById('contenedor-tabla-captura');
                    html2canvas(element, {{ scale: 2, backgroundColor: '#ffffff' }}).then(function(canvas) {{
                        canvas.toBlob(function(blob) {{
                            if (typeof ClipboardItem !== 'undefined' && navigator.clipboard && navigator.clipboard.write) {{
                                const item = new ClipboardItem({{"image/png": blob}});
                                navigator.clipboard.write([item]).then(function() {{
                                    alert("✅ Imagen copiada al portapapeles correctamente. ¡Ya puedes pegarla (Ctrl+V)!");
                                }}).catch(function(err) {{ descargar(canvas); }});
                            }} else {{ descargar(canvas); }}
                        }});
                    }});
                }}
                function descargar(canvas) {{
                    var link = document.createElement('a');
                    link.download = 'clasificacion_{tm.tournament_name.replace(" ", "_")}.png';
                    link.href = canvas.toDataURL('image/png');
                    link.click();
                    alert("📥 Tu navegador no soporta copiado directo. La imagen ha sido descargada.");
                }}
            </script>
        </body>
        </html>
        """
        iframe_height = 250 + (len(df) * 45)
        components.html(html_content, height=iframe_height, scrolling=True)
    else:
        st.info("Sin datos.")

# ==============================================================================
# 5.6 PÁGINA FASES FINALES
# Explicación: Gestiona semifinales y la gran final, integrando cuadros informativos e inyección de mapas base64.
# ==============================================================================
elif menu == "Fases Finales":
    st.header("🏆 Semifinales y Finales")
    def set_score_10_ff(key_input): st.session_state[key_input] = 10
    if tm.phase == 'clasificatoria':
        st.info(f"El torneo sigue en fase clasificatoria (Activos: {len([p for p in tm.players if p['name'] not in tm.eliminated_players])}).")
        st.write("---")
        st.subheader("⚙️ Generar Fases Finales")
        col_auto, col_force_f, col_force_s = st.columns(3)
        with col_auto:
            st.markdown("##### 🤖 Automático")
            st.caption("• 12-28 Jugs → Final Directa\n• 29+ Jugs → Semifinales")
            if st.button("Generar Automático", use_container_width=True, type="primary"):
                ok, msg = tm.generar_fase_final_auto(modo='auto')
                if ok: st.success(msg); time.sleep(1); st.rerun()
                else: st.error(msg)
        with col_force_f:
            st.markdown("##### 🏁 Forzar Final")
            st.caption("Requiere mín. 8 jugadores.")
            if st.button("Crear Final Directa", use_container_width=True):
                ok, msg = tm.generar_fase_final_auto(modo='final')
                if ok: st.success(msg); time.sleep(1); st.rerun()
                else: st.error(msg)
        with col_force_s:
            st.markdown("##### ⚔️ Forzar Semis")
            st.caption("Requiere mín. 16 jugadores.")
            if st.button("Crear Semifinales", use_container_width=True):
                ok, msg = tm.generar_fase_final_auto(modo='semifinal')
                if ok: st.success(msg); time.sleep(1); st.rerun()
                else: st.error(msg)
    elif tm.phase == 'semifinal':
        c_undo, c_title = st.columns([1, 4])
        with c_undo:
             if st.button("↩️ Deshacer", help="Volver a Clasificatoria"):
                 ok, msg = tm.deshacer_fase_final()
                 if ok: st.success(msg); time.sleep(1); st.rerun()
        with c_title:
             st.subheader("Cuadro de Semifinales")
        st.write("---")
        cols = st.columns(2)
        for k, mesa in tm.semifinal_tables.items():
            with cols[(k-1)//2]:
                with st.container(border=True):
                    st.write(f"**Semifinal {k}**")
                    sorted_mesa = sorted(mesa, key=lambda x: tm.seeds_fase_final.get(x, 9999))
                    order_str = " → ".join([f"{p} (Rank: {tm.seeds_fase_final.get(p, 9999)+1})" for p in sorted_mesa])
                    st.info(f"📢 **Elección (Turno, Asiento, Color):**\n{order_str}")
                    if k in tm.semifinal_results:
                        st.success("Jugada")
                        res = tm.semifinal_results[k]
                        data_semi_show = []
                        for p in mesa:
                            if p in res:
                                d = res[p]
                                data_semi_show.append({"Pos": d['P°'], "Jugador": p, "PV": d['PV'], "PM": d['PM'], "%V": f"{d['%V']:.1f}%"})
                        if data_semi_show:
                            data_semi_show.sort(key=lambda x: x['Pos'])
                            st.dataframe(pd.DataFrame(data_semi_show), hide_index=True)
                    with st.expander(f"Cargar/Editar Semifinal {k}", expanded=(k not in tm.semifinal_results)):
                        with st.form(f"semi_{k}"):
                            scores = {}
                            for p in mesa:
                                st.write(f"**{p}**")
                                c_in, c_btn = st.columns([3,1])
                                key_sm = f"sm_{k}_{p}"
                                if key_sm not in st.session_state: st.session_state[key_sm] = 2
                                with c_in: scores[p] = st.number_input("PM", 2, 10, key=key_sm, label_visibility="collapsed")
                                with c_btn: st.form_submit_button("10", on_click=set_score_10_ff, args=(key_sm,), use_container_width=True, key=f"btn_10_semi_{key_sm}")
                            adv_opts = ["Auto (Ranking)"] + mesa
                            winner_override = st.selectbox("Desempate manual", adv_opts, key=f"wo_{k}")
                            if st.form_submit_button("Guardar Resultado"):
                                w = None if winner_override == "Auto (Ranking)" else winner_override
                                ok, msg, desempates = tm.registrar_resultados_finales('semifinal', k, scores, w)
                                if ok:
                                    st.success(msg)
                                    if desempates:
                                        for d in desempates: st.info(d)
                                    time.sleep(1); st.rerun()

        st.markdown("---")
        st.markdown("### 📸 Exportar Cuadro de Semifinales")
        st.caption("Genera una imagen consolidada de las semifinales y su mapa oficial guardado para descargar.")

        try:
            html_semis: str = ""
            for k, mesa in tm.semifinal_tables.items():
                html_semis += f"<div class='mesa-card'><h4>Semifinal {k}</h4><ul>"
                for p in mesa:
                    html_semis += f"<li>{p}</li>"
                html_semis += "</ul></div>"

            key_map: str = "semifinal"
            mapa_img: str = str(tm.maps.get(key_map, ""))
            html_mapa: str = f"<div style='text-align:center; margin-top: 20px;'><img src='{mapa_img}' style='max-width: 90%; border-radius: 8px; border: 2px solid #2c3e50;'/></div>" if mapa_img else ""

            html_fixture_semifinal: str = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
                <style>
                    body {{ font-family: sans-serif; background-color: transparent; }}
                    #captura-semifinal {{ background-color: white; padding: 20px; border-radius: 10px; display: inline-block; width: 95%; box-sizing: border-box; }}
                    .mesas-grid {{ display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; margin-top: 15px; }}
                    .mesa-card {{ border: 2px solid #2c3e50; border-radius: 8px; padding: 10px; min-width: 180px; flex: 1 1 200px; max-width: 250px; background-color: #f8f9fa; box-shadow: 0 4px 6px rgba(0,0,0,0.1); box-sizing: border-box; }}
                    .mesa-card h4 {{ margin-top: 0; text-align: center; color: #f1c40f; background-color: #2c3e50; padding: 8px; border-radius: 5px 5px 0 0; margin: -10px -10px 10px -10px; }}
                    .mesa-card ul {{ list-style-type: none; padding-left: 0; margin-bottom: 0; }}
                    .mesa-card li {{ padding: 6px 0; border-bottom: 1px dashed #cccccc; text-align: center; font-weight: bold; color: #333333; }}
                    .mesa-card li:last-child {{ border-bottom: none; }}
                    .export-btn {{ background-color: #ff4b4b; color: white; border: none; padding: 10px 20px; font-size: 16px; cursor: pointer; border-radius: 8px; font-weight: bold; margin-bottom: 15px; }}
                    .export-btn:hover {{ background-color: #ff3333; }}
                </style>
            </head>
            <body>
                <button class="export-btn" onclick="capturar()">📸 Copiar Imagen al Portapapeles</button>
                <br>
                <div id="captura-semifinal">
                    <h2 style="text-align: center; color: #2c3e50; margin-bottom: 5px;">{tm.tournament_name}</h2>
                    <h4 style="text-align: center; color: #7f8c8d; margin-top: 0;">Fixture Oficial — Semifinales</h4>
                    <div class="mesas-grid">
                        {html_semis}
                    </div>
                    {html_mapa}
                </div>
                <script>
                    function capturar() {{
                        var element = document.getElementById('captura-semifinal');
                        html2canvas(element, {{ scale: 2, backgroundColor: '#ffffff' }}).then(function(canvas) {{
                            canvas.toBlob(function(blob) {{
                                if (typeof ClipboardItem !== 'undefined' && navigator.clipboard && navigator.clipboard.write) {{
                                    const item = new ClipboardItem({{"image/png": blob}});
                                    navigator.clipboard.write([item]).then(function() {{
                                        alert("✅ Imagen de Semifinales copiada al portapapeles correctamente.");
                                    }}).catch(function() {{ descargar(canvas); }});
                                }} else {{ descargar(canvas); }}
                            }});
                        }});
                    }}
                    function descargar(canvas) {{
                        var link = document.createElement('a');
                        link.download = 'fixture_semifinal_{tm.tournament_name.replace(" ", "_")}.png';
                        link.href = canvas.toDataURL('image/png');
                        link.click();
                        alert("📥 Imagen descargada.");
                    }}
                </script>
            </body>
            </html>
            """
            iframe_height_semifinal: int = 350 + (500 if mapa_img else 0)
            components.html(html_fixture_semifinal, height=iframe_height_semifinal, scrolling=True)
        except Exception as export_error:
            st.error(f"Error al generar la vista de exportación de semifinales: {str(export_error)}")

    elif tm.phase == 'final':
        c_undo, c_title = st.columns([1, 4])
        with c_undo:
             if st.button("↩️ Deshacer", help="Volver a Clasificatoria"):
                 ok, msg = tm.deshacer_fase_final()
                 if ok: st.success(msg); time.sleep(1); st.rerun()
        with c_title:
             st.subheader("👑 GRAN FINAL")
        if tm.semifinal_results:
             with st.expander("Ver Resultados Semifinales"):
                 for k, mesa in tm.semifinal_tables.items():
                     st.markdown(f"**Semifinal {k}**")
                     if k in tm.semifinal_results:
                         res = tm.semifinal_results[k]
                         data_semi_show = []
                         for p in mesa:
                             if p in res:
                                 d = res[p]
                                 data_semi_show.append({"Pos": d['P°'], "Jugador": p, "PV": d['PV'], "PM": d['PM'], "%V": f"{d['%V']:.1f}%"})
                         if data_semi_show:
                             data_semi_show.sort(key=lambda x: x['Pos'])
                             st.dataframe(pd.DataFrame(data_semi_show), hide_index=True)
                 with st.popover(f"Editar Semifinal {k}"):
                     with st.form(f"edit_semi_{k}_finalphase"):
                        scores = {}
                        for p in mesa:
                            curr_val = res[p]['PM'] if p in res else 2
                            st.write(f"**{p}**")
                            c_in, c_btn = st.columns([3,1])
                            key_ed = f"ed_sm_{k}_{p}"
                            if key_ed not in st.session_state: st.session_state[key_ed] = int(curr_val)
                            with c_in: scores[p] = st.number_input("PM", 2, 10, key=key_ed, label_visibility="collapsed")
                            with c_btn: st.form_submit_button("10", on_click=set_score_10_ff, args=(key_ed,), use_container_width=True, key=f"btn_10_ed_{key_ed}")
                        adv_opts = ["Auto (Ranking)"] + mesa
                        winner_override = st.selectbox("Desempate manual", adv_opts, key=f"ed_wo_{k}")
                        if st.form_submit_button("Actualizar Resultado"):
                            w = None if winner_override == "Auto (Ranking)" else winner_override
                            ok, msg, desempates = tm.registrar_resultados_finales('semifinal', k, scores, w)
                            if ok: st.success("Actualizado"); time.sleep(1); st.rerun()
        st.write("Mesa Final:", ", ".join(tm.final_table))
        sorted_by_rank = sorted(tm.final_table, key=lambda x: tm.seeds_fase_final.get(x, 9999))
        st.info(f"📢 **Ventaja Deportiva (Turno, Asiento y Color):** Eligen en este orden según Ranking General: " + " → ".join([f"**{i+1}. {p}**" for i, p in enumerate(sorted_by_rank)]))

        st.markdown("---")
        st.markdown("### 📸 Exportar Cuadro de la Gran Final")
        st.caption("Genera una imagen consolidada de la mesa final y su mapa guardado para descargar.")

        html_final = f"<div class='mesa-card'><h4>👑 GRAN FINAL</h4><ul>"
        for p in tm.final_table:
            html_final += f"<li>{p}</li>"
        html_final += f"</ul></div>"

        key_map_f = "final"
        mapa_img_f = tm.maps.get(key_map_f, "")
        html_mapa_f = f"<div style='text-align:center; margin-top: 20px;'><img src='{mapa_img_f}' style='max-width: 90%; border-radius: 8px; border: 2px solid #2c3e50;'/></div>" if mapa_img_f else ""

        html_fixture_final = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
            <style>
                body {{ font-family: sans-serif; background-color: transparent; }}
                #captura-final {{ background-color: white; padding: 20px; border-radius: 10px; display: inline-block; width: 95%; box-sizing: border-box; }}
                .mesas-grid {{ display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; margin-top: 15px; }}
                .mesa-card {{ border: 2px solid #2c3e50; border-radius: 8px; padding: 10px; min-width: 180px; flex: 1 1 200px; max-width: 250px; background-color: #f8f9fa; box-shadow: 0 4px 6px rgba(0,0,0,0.1); box-sizing: border-box; }}
                .mesa-card h4 {{ margin-top: 0; text-align: center; color: #f1c40f; background-color: #2c3e50; padding: 8px; border-radius: 5px 5px 0 0; margin: -10px -10px 10px -10px; }}
                .mesa-card ul {{ list-style-type: none; padding-left: 0; margin-bottom: 0; }}
                .mesa-card li {{ padding: 6px 0; border-bottom: 1px dashed #cccccc; text-align: center; font-weight: bold; color: #333333; }}
                .mesa-card li:last-child {{ border-bottom: none; }}
                .export-btn {{ background-color: #ff4b4b; color: white; border: none; padding: 10px 20px; font-size: 16px; cursor: pointer; border-radius: 8px; font-weight: bold; margin-bottom: 15px; }}
                .export-btn:hover {{ background-color: #ff3333; }}
            </style>
        </head>
        <body>
            <button class="export-btn" onclick="capturar()">📸 Copiar Imagen al Portapapeles</button>
            <br>
            <div id="captura-final">
                <h2 style="text-align: center; color: #2c3e50; margin-bottom: 5px;">{tm.tournament_name}</h2>
                <h4 style="text-align: center; color: #7f8c8d; margin-top: 0;">Fixture Oficial — Gran Final</h4>
                <div class="mesas-grid">
                    {html_final}
                </div>
                {html_mapa_f}
            </div>
            <script>
                function capturar() {{
                    var element = document.getElementById('captura-final');
                    html2canvas(element, {{ scale: 2, backgroundColor: '#ffffff' }}).then(function(canvas) {{
                        canvas.toBlob(function(blob) {{
                            if (typeof ClipboardItem !== 'undefined' && navigator.clipboard && navigator.clipboard.write) {{
                                const item = new ClipboardItem({{"image/png": blob}});
                                navigator.clipboard.write([item]).then(function() {{
                                    alert("✅ Imagen de la Final copiada al portapapeles correctamente.");
                                }}).catch(function() {{ descargar(canvas); }});
                            }} else {{ descargar(canvas); }}
                        }});
                    }});
                }}
                function descargar(canvas) {{
                    var link = document.createElement('a');
                    link.download = 'fixture_final_{tm.tournament_name.replace(" ", "_")}.png';
                    link.href = canvas.toDataURL('image/png');
                    link.click();
                    alert("📥 Imagen descargada.");
                }}
            </script>
        </body>
        </html>
        """
        components.html(html_fixture_final, height=iframe_height_final, scrolling=True)

        if tm.final_results:
            st.balloons()
            st.success("¡Torneo Finalizado!")
            res = tm.final_results
            sorted_p = sorted(tm.final_table, key=lambda x: res[x]['P°'])
            st.markdown(f"## 🥇 CAMPEÓN: {sorted_p[0]}")
            st.markdown(f"🥈 Subcampeón: {sorted_p[1]}")
            st.markdown(f"🥉 Tercero: {sorted_p[2]}")
            if len(sorted_p) > 3: st.markdown(f"4️⃣ Cuarto Lugar: {sorted_p[3]}")
            st.markdown("##### 📊 Tabla de Resultados Final")
            data_show = []
            for p in sorted_p:
                d = res[p]
                data_show.append({"Pos": d['P°'], "Jugador": p, "PV": d['PV'], "PM": d['PM'], "%V": f"{d['%V']:.1f}%"})
            if data_show:
                df_show = pd.DataFrame(data_show)
                st.dataframe(df_show, hide_index=True)
            st.divider()
            with st.expander("🛠️ Corregir Resultados Finales"):
                with st.form("final_form_edit"):
                    scores = {}
                    c = st.columns(len(tm.final_table))
                    for i, p in enumerate(tm.final_table):
                        current_pm = tm.final_results[p]['PM']
                        with c[i]:
                            st.write(f"**{p}**")
                            c_in, c_btn = st.columns([3,1])
                            key_fin_ed = f"fin_edit_{p}"
                            if key_fin_ed not in st.session_state: st.session_state[key_fin_ed] = int(current_pm)
                            with c_in: scores[p] = st.number_input("PM", 2, 10, key=key_fin_ed, label_visibility="collapsed")
                            with c_btn: st.form_submit_button("10", on_click=set_score_10_ff, args=(key_fin_ed,), use_container_width=True, key=f"btn_10_final_ed_{key_fin_ed}")
                    if st.form_submit_button("Actualizar Resultado Final"):
                        ok, msg, desempates = tm.registrar_resultados_finales('final', 0, scores)
                        if ok: st.success("Actualizado correctamente"); time.sleep(1); st.rerun()
        else:
            with st.form("final_form"):
                scores = {}
                c = st.columns(4)
                for i, p in enumerate(tm.final_table):
                    with c[i]:
                        st.write(f"**{p}**")
                        c_in, c_btn = st.columns([3,1])
                        key_fin = f"fin_{p}"
                        if key_fin not in st.session_state: st.session_state[key_fin] = 2
                        with c_in: scores[p] = st.number_input("PM", 2, 10, key=key_fin, label_visibility="collapsed")
                        with c_btn: st.form_submit_button("10", on_click=set_score_10_ff, args=(key_fin,), use_container_width=True, key=f"btn_10_final_{key_fin}")
                if st.form_submit_button("Coronar Campeón"):
                    ok, msg, desempates = tm.registrar_resultados_finales('final', 0, scores)
                    if ok: st.success(msg)
                    st.rerun()
        if tm.final_results:
            sorted_p_check = sorted(tm.final_table, key=lambda x: tm.final_results[x]['P°'])
            msgs_desempate_fixed = []
            for i in range(len(sorted_p_check) - 1):
                p1, p2 = sorted_p_check[i], sorted_p_check[i+1]
                d1, d2 = tm.final_results[p1], tm.final_results[p2]
                if d1['PM'] == d2['PM'] and d1['PV'] == d2['PV']:
                    s1 = tm.seeds_fase_final.get(p1, 999) + 1
                    s2 = tm.seeds_fase_final.get(p2, 999) + 1
                    msgs_desempate_fixed.append(f"ℹ️ **{p1}** (#{s1}) gana posición a **{p2}** (#{s2}) por Ranking.")
            if msgs_desempate_fixed:
                for m in msgs_desempate_fixed: st.info(m)

# 5.7 PÁGINA: APUESTAS
# Explicación: Sistema de apuestas tote con cuotas dinámicas, validación de banca y liquidación automática.
elif menu == "Apuestas":
    st.header("🎰 Sistema de Apuestas (Tote Blindado)")
    if tm.phase != 'final' or not tm.final_table:
        st.warning("⚠️ Las apuestas solo están disponibles cuando se ha generado la **Mesa Final**.")
        st.info(f"Fase actual: {tm.phase.upper()}")
    else:
        total_pool = sum(b['monto'] for b in tm.bets)
        col_st1, col_st2, col_st3 = st.columns(3)
        with col_st1:
            st.metric("💰 Pozo Total", f"${total_pool:,.0f}", delta=f"{len(tm.bets)} apuestas")
        with col_st2:
            status_label = "ABIERTO 🟢" if tm.betting_open else "CERRADO 🔴"
            st.metric("Estado", status_label)
        with col_st3:
            st.metric("Banca Respaldo", f"${tm.house_bankroll:,.0f}")
        st.write("---")
        with st.expander("🛠️ Panel de Control (Admin)", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Control de Estado**")
                if not tm.betting_open:
                    if st.button("🟢 ABRIR APUESTAS", type="primary", use_container_width=True):
                        ok, msg = tm.abrir_apuestas()
                        if ok: st.success(msg); st.rerun()
                else:
                    if st.button("🔴 CERRAR APUESTAS", type="primary", use_container_width=True):
                        ok, msg = tm.cerrar_apuestas()
                        if ok: st.warning(msg); st.rerun()
                st.write("")
                if st.button("🗑️ REINICIAR TODO (Borrar Apuestas)", help="Elimina todas las apuestas registradas y deja el pozo en 0"):
                    ok, msg = tm.reiniciar_apuestas()
                    if ok:
                        st.toast(msg, icon="🗑️")
                        time.sleep(1)
                        st.rerun()
            with c2:
                st.markdown("**Gestión de Banca**")
                new_bankroll = st.number_input("💰 Ajustar Banca Respaldo", value=int(tm.house_bankroll), step=50000)
                if new_bankroll != tm.house_bankroll:
                    tm.house_bankroll = new_bankroll
                    tm.save_state()
                    st.toast("Banca actualizada")
        st.subheader("📊 Panel de Finalistas")
        probs_teoricas = tm._calcular_probabilidades_final()
        pool_total, odds_live, counts_live, amounts_live, betting_fav, dynamic_floors = tm.calcular_odds_tote_wrapper()
        ranked_finalists = tm._get_sorted_finalists()
        cols = st.columns(len(tm.final_table))
        for i, p in enumerate(tm.final_table):
            with cols[i]:
                prob = probs_teoricas.get(p, 0)
                factor_pago = odds_live.get(p, 0.0)
                rank_idx = ranked_finalists.index(p) if p in ranked_finalists else 3
                role_label = "Aspirante"
                role_icon = "🎲"
                if rank_idx == 0: role_label="Favorito"; role_icon="⭐"
                elif rank_idx == 1: role_label="2do Probable"; role_icon="🥈"
                elif rank_idx == 2: role_label="3er Probable"; role_icon="🥉"
                elif rank_idx == 3: role_label="Underdog"; role_icon="🐕"
                with st.container(border=True):
                    st.markdown(f"<div class='bet-card-header'>{role_icon} {p}</div>", unsafe_allow_html=True)
                    st.caption(f"{role_label}")
                    if factor_pago > 0:
                        st.markdown(f"<div class='bet-odds-display'>x{factor_pago:.2f}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='bet-odds-display'>---</div>", unsafe_allow_html=True)
                    st.progress(prob / 100)
                    st.caption(f"Prob. Técnica: {prob:.1f}%")
                    c_f1, c_f2 = st.columns(2)
                    c_f1.metric("Apoyos", counts_live.get(p, 0))
                    c_f2.metric("Monto", f"${amounts_live.get(p, 0)/1000:,.0f}k")
                    if p == betting_fav:
                        st.markdown(":fire: **Fav. Público**")
        st.divider()
        if tm.betting_open:
            st.subheader("📝 Realizar Apuesta")
            c_input_left, c_input_right = st.columns([1, 1])
            with c_input_left:
                st.markdown("##### 1. ¿Quién Apuesta?")
                tab_reg, tab_guest = st.tabs(["Usuario Registrado", "Invitado"])
                apostador_final = None
                with tab_reg:
                    all_players = sorted([p['name'] for p in tm.players if p['name'] not in tm.final_table])
                    apostador_sel = st.selectbox("Seleccionar Jugador", ["..."] + all_players, key="sel_reg")
                    if apostador_sel != "...": apostador_final = apostador_sel
                    if not all_players:
                        st.caption("Nota: Los finalistas no aparecen en esta lista porque no pueden apostar.")
                with tab_guest:
                    apostador_input = st.text_input("Nombre Invitado", placeholder="Ej: Juan Perez", key="inp_guest")
                    if apostador_input.strip(): apostador_final = apostador_input.strip() + " (Ext)"
                st.markdown("##### 2. ¿A quién le vas?")
                candidato = st.selectbox("Finalista", ["..."] + tm.final_table)
                st.markdown("##### 3. ¿Cuánto?")
                monto = st.select_slider("Monto", options=CONSTANTS['BET_AMOUNTS'], value=1000)
            with c_input_right:
                st.markdown("##### 🎫 Ticket Simulado")
                if candidato != "..." and monto > 0:
                    simulation = tm.simular_pago(candidato, monto)
                    if simulation:
                        st.markdown(f"""
                        <div class="ticket-container">
                            <h4>APUESTA POTENCIAL</h4>
                            <p>Si <b>{candidato}</b> gana...</p>
                            <h2>Posibilidad de cobrar: ${simulation['win_amount']:,.0f}</h2>
                            <p style="color: gray">Factor est: x{simulation['dividend']:.2f}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        if simulation['is_capped']:
                            st.caption("🛑 Tope Máximo (x3.5) activado.")
                        st.write("")
                        if st.button("✅ CONFIRMAR APUESTA", type="primary", use_container_width=True):
                            if not apostador_final:
                                st.error("Falta nombre del apostador.")
                            else:
                                ok, msg = tm.registrar_apuesta(apostador_final, candidato, monto)
                                if ok:
                                    st.balloons()
                                    st.success(msg)
                                    time.sleep(1.5)
                                    st.rerun()
                                else: st.error(msg)
                else:
                    st.info("Completa los datos para ver el ticket.")
        else:
            if not tm.final_results:
                st.info("⏳ Las apuestas están cerradas. Esperando resultado final...")
            else:
                st.success("✅ Torneo Finalizado. Resultados disponibles.")
        if tm.betting_results_log:
            st.divider()
            st.header("🧾 Liquidación")
            for line in tm.betting_results_log:
                if "GANADOR" in line: st.success(line)
                elif "✅" in line: st.markdown(f"**{line}**")
                else: st.write(line)
        st.divider()
        with st.expander(f"📋 Ver Apuestas Registradas ({len(tm.bets)})", expanded=False):
            if tm.bets:
                for i, bet in enumerate(tm.bets):
                    c1, c2, c3, c4, c5 = st.columns([0.5, 2, 2, 1.5, 1])
                    c1.write(f"#{i+1}")
                    c2.write(f"**{bet['apostador']}**")
                    c3.write(f"→ {bet['candidato']}")
                    c4.write(f"${bet['monto']:,.0f}")
                    if tm.betting_open:
                        if c5.button("🗑️", key=f"del_bet_{i}"):
                            ok, msg = tm.eliminar_apuesta(i)
                            if ok: st.rerun()
            else:
                st.caption("No hay apuestas.")
        st.divider()
        with st.expander("ℹ️ ¿Cómo funciona el sistema de apuestas?"):
            st.markdown("""
            **Sistema de Apuestas Dinámicas (Tote Blindado)**
            1. **Cuotas Variables:** Si mucha gente apuesta al Candidato A, su cuota de pago baja; si nadie apuesta al B, su cuota sube.
            2. **El Ticket es Estimado:** El valor mostrado es con apuestas actuales; si entran más apuestas al mismo candidato, el premio final puede bajar.
            3. **Topes y Pisos:** Piso mínimo x1.0 (recuperas inversión), Tope máximo x3.5.
            4. **La Banca:** Fondo de reserva para asegurar pagos si el pozo no alcanza.
            """)

# 5.8 PÁGINA: EXPORTAR
# Explicación: Genera un archivo Excel con todas las hojas: ranking, detalle de resultados y fixture.
elif menu == "Exportar":
    st.header("💾 Exportar Datos")
    if st.button("Generar Excel Resultados"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            data = tm._obtener_ranking_data()
            pd.DataFrame(data).to_excel(writer, sheet_name='Ranking', index=False)
            all_res = []
            for (r, t), res in tm.results.items():
                for p, d in res.items():
                    all_res.append({'Ronda': r, 'Mesa': t, 'Jugador': p, **d})
            if all_res: pd.DataFrame(all_res).to_excel(writer, sheet_name='Detalle', index=False)
            data_mesas = []
            for i, r in enumerate(tm.rounds):
                for t_idx, mesa in enumerate(r['tables']):
                    for p in mesa:
                        data_mesas.append({"Ronda": i+1, "Mesa": t_idx+1, "Jugador": p})
            if data_mesas: pd.DataFrame(data_mesas).to_excel(writer, sheet_name='Fixture', index=False)
        output.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        file_name = f"Torneo_Catan_{timestamp}.xlsx"
        st.download_button(label="📥 Descargar Excel", data=output, file_name=file_name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# 5.9 PÁGINA: TEMPORIZADOR
# Explicación: Cuenta regresiva configurable (45/60 minutos o personalizado) con alarma visual y sonora.
elif menu == "Temporizador":
    st.header("⏱️ Control de Tiempo de Ronda")
    if st.session_state.timer_end:
        with st.container(border=True):
            components.html(get_timer_html(target_timestamp=st.session_state.timer_end, is_big=True), height=400)
        c1, c2, c3, c4 = st.columns([1, 1, 1.5, 1.5])
        with c1:
            if st.button("⏸ PAUSAR", use_container_width=True):
                remaining = st.session_state.timer_end - time.time()
                if remaining > 0:
                    st.session_state.timer_paused_left = remaining
                    st.session_state.timer_end = None
                    st.rerun()
        with c2:
            if st.button("⏹ DETENER", type="primary", use_container_width=True):
                st.session_state.timer_end = None
                st.rerun()
        with c3:
            if st.button("➕ 2 Min", use_container_width=True):
                st.session_state.timer_end += (2 * 60)
                st.rerun()
        with c4:
            if st.button("➕ 5 Min", use_container_width=True):
                st.session_state.timer_end += (5 * 60)
                st.rerun()
    elif st.session_state.timer_paused_left is not None:
        with st.container(border=True):
            components.html(get_timer_html(paused_seconds=st.session_state.timer_paused_left, is_big=True), height=400)
        st.warning("⚠️ El tiempo está detenido.")
        c1, c2 = st.columns([1, 4])
        with c1:
             if st.button("▶️ REANUDAR", type="primary", use_container_width=True):
                st.session_state.timer_end = time.time() + st.session_state.timer_paused_left
                st.session_state.timer_paused_left = None
                st.rerun()
        with c2:
             if st.button("⏹ REINICIAR TODO", use_container_width=True):
                st.session_state.timer_paused_left = None
                st.session_state.timer_end = None
                st.rerun()
    else:
        st.info("No hay ninguna ronda cronometrada en curso.")
        st.markdown("### Configurar Nuevo Timer")
        c1, c2, c3 = st.columns(3)
        with c1:
            with st.container(border=True):
                st.markdown("<h3 style='text-align: center;'>45 Min</h3>", unsafe_allow_html=True)
                if st.button("Iniciar 45'", use_container_width=True, type="primary"):
                    st.session_state.timer_end = time.time() + (45 * 60)
                    st.session_state.timer_paused_left = None
                    st.rerun()
        with c2:
            with st.container(border=True):
                st.markdown("<h3 style='text-align: center;'>60 Min</h3>", unsafe_allow_html=True)
                if st.button("Iniciar 60'", use_container_width=True, type="primary"):
                    st.session_state.timer_end = time.time() + (60 * 60)
                    st.session_state.timer_paused_left = None
                    st.rerun()
        with c3:
            with st.container(border=True):
                st.markdown("<h3 style='text-align: center;'>Personalizado</h3>", unsafe_allow_html=True)
                custom_min = st.number_input("Minutos", min_value=1, max_value=120, value=50)
                if st.button("Iniciar Manual", use_container_width=True):
                    st.session_state.timer_end = time.time() + (custom_min * 60)
                    st.session_state.timer_paused_left = None
                    st.rerun()
    st.divider()
    st.caption("Nota: El reloj cambiará a rojo cuando falten 5 minutos y sonará una alarma al terminar.")

# 5.10 PÁGINA: SORTEO
# Explicación: Selecciona aleatoriamente 3 ganadores entre jugadores activos con efectos de audio y cuenta regresiva.
elif menu == "Sorteo":
    st.header("🎁 Sorteo de Premios")
    st.markdown("Elige aleatoriamente un ganador entre los **jugadores activos**.")

    audio_cheer_placeholder = st.empty()

    lista_jugadores = [p['name'] for p in tm.players if p['name'] not in tm.eliminated_players]
    if len(lista_jugadores) < 3:
        st.warning(f"Se necesitan al menos 3 jugadores activos para realizar este sorteo (Hay {len(lista_jugadores)}).")
    else:
        col_girar, col_reset = st.columns([3, 1])
        with col_girar: iniciar = st.button("🎰 Girar la Tómbola", type="primary", use_container_width=True)
        with col_reset:
            if st.button("🔄 Reiniciar", use_container_width=True): st.rerun()
        st.caption(f"Participando: {len(lista_jugadores)} jugadores activos.")
        with st.expander("📋 Ver lista de participantes en el sorteo"):
            df_sorteo = pd.DataFrame(lista_jugadores, columns=["Jugadores Habilitados"])
            df_sorteo.index += 1
            st.dataframe(df_sorteo, use_container_width=True)

        if iniciar:
            uid = str(int(time.time() * 1000))
            audio_drum_placeholder = st.empty()
            audio_drum_placeholder.markdown(
                f'<audio autoplay style="display:none;"><source src="https://www.myinstants.com/media/sounds/drum-roll-sound-effect.mp3?v={uid}" type="audio/mpeg"></audio>',
                unsafe_allow_html=True
            )

            caja_conteo = st.empty()
            for i in range(10, 0, -1):
                caja_conteo.markdown(f"<h1 style='text-align: center; font-size: 80px;'>⏳ {i}</h1>", unsafe_allow_html=True)
                time.sleep(1)
            caja_conteo.empty()
            audio_drum_placeholder.empty()

            ganadores = random.sample(lista_jugadores, 3)
            ganador_principal = ganadores[0]
            suplente_1 = ganadores[1]
            suplente_2 = ganadores[2]

            st.balloons()
            audio_cheer_placeholder.markdown(
                f'<audio autoplay style="display:none;"><source src="https://www.myinstants.com/media/sounds/kids_cheering.mp3?v={uid}" type="audio/mpeg"></audio>',
                unsafe_allow_html=True
            )

            st.markdown(f"""
            <div style='text-align: center; padding: 20px; background-color: #d4edda; border-radius: 10px; border: 2px solid #28a745;'>
                <h3>🎉 ¡FELICIDADES! 🎉</h3>
                <h1 style='color: #155724; font-size: 50px;'>{ganador_principal}</h1>
                <p>Has ganado el sorteo.</p>
            </div>
            """, unsafe_allow_html=True)
            st.divider()
            c_sup1, c_sup2 = st.columns(2)
            with c_sup1: st.info(f"🥈 **1er Suplente:**\n\n{suplente_1}")
            with c_sup2: st.warning(f"🥉 **2do Suplente:**\n\n{suplente_2}")
            st.caption("Nota: Si el ganador no está, pasa al 1er suplente. Si este tampoco está, pasa al 2do suplente.")

# ==============================================================================
# 5.11 PÁGINA: GENERADOR DE MAPAS
# Explicación: Integra el generador con persistencia de estado y validación visual mediante umbrales de espectro HSV.
# ==============================================================================
elif menu == "Generador de Mapas":
    st.header("🗺️ Generador de Mapas de Catan")
    st.markdown("Genera un tablero balanceado o aleatorio directamente aquí. (Requiere conexión a internet)")
    components.iframe("https://catan.bunge.io/", height=750, scrolling=True)


# ==============================================================================
# 6. BOOTSTRAP DE EJECUCIÓN NATIVA (EXE / STANDALONE)
# Responsabilidad: Interceptar la ejecución directa delegando el control al núcleo de Streamlit, previniendo recursión y colisiones de Runtime.
# ==============================================================================
if __name__ == "__main__":
    import sys
    import os

    try:
        from streamlit.web import cli as stcli
        from streamlit import runtime
        
        # Verificación estricta del motor de Streamlit:
        # Si el Runtime NO existe, el script fue ejecutado crudo (doble clic). Lo iniciamos.
        # Si el Runtime SÍ existe, Streamlit ya está controlando el flujo. Lo ignoramos para evitar bucles.
        if not runtime.exists():
            print("🚀 Iniciando servidor embebido de Catan Manager...")
            # Sobrescribimos sys.argv para emular el comando nativo de terminal
            sys.argv = ["streamlit", "run", os.path.abspath(__file__), "--global.developmentMode=false"]
            sys.exit(stcli.main())
            
    except ImportError as e:
        print(f"❌ Error de Dependencia Core: {str(e)}")
        input("Presiona Enter para salir...")
        sys.exit(1)
    except SystemExit as e:
        # Cierre limpio del servidor interceptado para evitar trazas rojas en consola
        sys.exit(e.code)
    except Exception as e:
        print(f"❌ Error crítico de inicialización: {str(e)}")
        input("Presiona Enter para salir...")
        sys.exit(1)
