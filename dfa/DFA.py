from collections import defaultdict, deque
from typing import Dict, FrozenSet, Iterable, List, Set, Tuple, Optional
import json

from nfa.State import State
from nfa.NFA import NFA
from lib.utils import merge_overlapping_ranges, symbol_is_subsumed


class DFA:

    def __init__(self, start: State, accepting_states: Set[State]) -> None:
        self._start = start

        self._accepting_states = accepting_states if accepting_states else set()

    @staticmethod
    def epsilon_closure(states: Iterable[State]) -> FrozenSet[State]:
        closure = set(states)
        stack = list(states)
        while stack:
            curr = stack.pop()
            for eps_state in curr.transitions.get("ε", []):
                if eps_state not in closure:
                    closure.add(eps_state)
                    stack.append(eps_state)
        return frozenset(closure)

    @staticmethod
    def move(states: Iterable[State], symbol: str) -> FrozenSet[State]:
        reachable = set()
        for state in states:
            if symbol in state.transitions:
                reachable.update(state.transitions[symbol])
        return frozenset(reachable)

    @staticmethod
    def subset_construction(
        nfa: NFA,
    ) -> Tuple[
        Set[FrozenSet[State]],
        Dict[Tuple[FrozenSet[State], str], FrozenSet[State]],
        FrozenSet[State],
        List[str],
        State,
    ]:
        symbols = nfa.nfa_symbols()
        start_closure = DFA.epsilon_closure([nfa.start])

        dfa_transitions: Dict[Tuple[FrozenSet[State], str], FrozenSet[State]] = {}
        queue = deque([start_closure])
        visited = {start_closure}

        while queue:
            curr_states = queue.popleft()
            for symbol in symbols:
                target_states = DFA.move(curr_states, symbol)
                if not target_states:
                    continue

                next_states = DFA.epsilon_closure(target_states)

                dfa_transitions[(curr_states, symbol)] = next_states
                if next_states not in visited:
                    visited.add(next_states)
                    queue.append(next_states)

        return visited, dfa_transitions, start_closure, symbols, nfa.end

    @staticmethod
    def hopcroft(
        dfa_states: Set[FrozenSet[State]],
        dfa_transitions: Dict[Tuple[FrozenSet[State], str], FrozenSet[State]],
        nfa_accept_state: State,
        symbols: List[str],
    ) -> Tuple[List[Set[FrozenSet[State]]], Set[FrozenSet[State]]]:

        accepting = {s for s in dfa_states if nfa_accept_state in s}
        non_accepting = dfa_states - accepting

        P: List[Set[FrozenSet[State]]] = []
        W: List[Set[FrozenSet[State]]] = []

        if accepting:
            P.append(accepting)
            W.append(accepting)
        if non_accepting:
            P.append(non_accepting)
            W.append(non_accepting)

        inverse_transitions: Dict[
            FrozenSet[State], Dict[str, List[FrozenSet[State]]]
        ] = defaultdict(lambda: defaultdict(list))
        for (src, symbol), tgt in dfa_transitions.items():
            inverse_transitions[tgt][symbol].append(src)

        while W:
            A = W.pop()
            for symbol in symbols:

                X = set()
                for target_in_A in A:
                    if target_in_A in inverse_transitions:
                        X.update(inverse_transitions[target_in_A].get(symbol, []))

                if not X:
                    continue

                splits = []
                for i, Y in enumerate(P):
                    Y_int = Y & X
                    Y_diff = Y - X
                    if Y_int and Y_diff:
                        splits.append((i, Y, Y_int, Y_diff))

                for i, Y, Y_int, Y_diff in reversed(splits):
                    P[i] = Y_int
                    P.append(Y_diff)

                    if Y in W:
                        W.remove(Y)
                        W.append(Y_int)
                        W.append(Y_diff)
                    else:

                        W.append(Y_int if len(Y_int) <= len(Y_diff) else Y_diff)

        return P, accepting

    @staticmethod
    def build_minimized_dfa(nfa: NFA) -> "DFA":
        dfa_states, dfa_transitions, start_state, symbols, nfa_end = (
            DFA.subset_construction(nfa)
        )
        partitions, accepting_groups = DFA.hopcroft(
            dfa_states, dfa_transitions, nfa_end, symbols
        )
        minimized_dfa = DFA._build_from_partitions(
            partitions, accepting_groups, dfa_transitions, start_state, symbols
        )
        minimized_dfa.simplify_transitions()
        return minimized_dfa

    @staticmethod
    def _build_from_partitions(
        P: List[Set[FrozenSet[State]]],
        accepting_groups: Set[FrozenSet[State]],
        dfa_transitions: Dict[Tuple[FrozenSet[State], str], FrozenSet[State]],
        start_dfa_state: FrozenSet[State],
        symbols: List[str],
    ) -> "DFA":
        old_to_new_map: Dict[FrozenSet[State], State] = {}

        for i, group in enumerate(P):
            new_state = State(id=i)
            for old_state in group:
                old_to_new_map[old_state] = new_state

        min_start = old_to_new_map[start_dfa_state]
        min_accepting = {old_to_new_map[s] for s in accepting_groups}

        for group in P:
            representative = next(iter(group))
            src_state = old_to_new_map[representative]

            for symbol in symbols:
                target_group = dfa_transitions.get((representative, symbol))
                if target_group and target_group in old_to_new_map:
                    dst_state = old_to_new_map[target_group]
                    src_state.add_transition(symbol, dst_state)

        return DFA(min_start, min_accepting)

    def simplify_transitions(self) -> None:
        visited = {self._start.name}
        queue = deque([self._start])

        while queue:
            curr = queue.popleft()

            target_map: Dict[State, List[str]] = defaultdict(list)
            for symbol, targets in curr.transitions.items():
                for target in targets:
                    target_map[target].append(symbol)

            curr.transitions.clear()
            for target, symbols in target_map.items():
                merged_symbols = self._merge_symbol_list(symbols)
                for sym in merged_symbols:
                    curr.transitions[sym] = [target]

            for targets in curr.transitions.values():
                for state in targets:
                    if state.name not in visited:
                        visited.add(state.name)
                        queue.append(state)

    @staticmethod
    def _merge_symbol_list(symbols: List[str]) -> List[str]:
        if not symbols:
            return []

        kept = []
        for s in symbols:
            if not any(symbol_is_subsumed(s, other) for other in symbols if s != other):
                kept.append(s)

        changed = True
        while changed:
            changed = False
            kept.sort()
            for i, s1 in enumerate(kept):
                for j, s2 in enumerate(kept[i + 1 :], start=i + 1):
                    merged = merge_overlapping_ranges(s1, s2)
                    if merged:
                        kept.remove(s1)
                        kept.remove(s2)
                        kept.append(merged)
                        changed = True
                        break
                if changed:
                    break

        return kept

    def to_dict(self) -> dict:
        result = {"startingState": self._start.name}
        visited = {self._start.name}
        queue = deque([self._start])

        while queue:
            curr = queue.popleft()
            is_accepting = curr in self._accepting_states

            entry = {"isTerminatingState": is_accepting}
            for symbol, next_states in curr.transitions.items():
                names = [s.name for s in next_states]
                entry[symbol] = names[0] if len(names) == 1 else names

                for s in next_states:
                    if s.name not in visited:
                        visited.add(s.name)
                        queue.append(s)

            result[curr.name] = entry

        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
