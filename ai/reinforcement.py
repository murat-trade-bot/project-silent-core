import random
import numpy as np

class ReinforcementAgent:
    def __init__(self, actions=["BUY", "SELL", "HOLD"], alpha=0.1, gamma=0.9, epsilon=0.1):
        self.q_table = {}
        self.actions = actions
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon

    def get_state_key(self, state):
        return tuple(state.items())

    def get_action(self, state):
        key = self.get_state_key(state)
        if random.random() < self.epsilon or key not in self.q_table:
            return random.choice(self.actions)
        return max(self.q_table[key], key=self.q_table[key].get)

    def update_policy(self, state, action, reward, next_state):
        key = self.get_state_key(state)
        next_key = self.get_state_key(next_state)
        if key not in self.q_table:
            self.q_table[key] = {a: 0 for a in self.actions}
        if next_key not in self.q_table:
            self.q_table[next_key] = {a: 0 for a in self.actions}
        predict = self.q_table[key][action]
        target = reward + self.gamma * max(self.q_table[next_key].values())
        self.q_table[key][action] += self.alpha * (target - predict)
    # Gelişmiş derin öğrenme yöntemleri (DQN/PPO) entegre edilebilir. 