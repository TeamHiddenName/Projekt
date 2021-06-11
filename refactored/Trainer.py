import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from Model import Net
from ExperienceBuffer import ExperienceReplay
from kaggle_environments import make




class Trainer:
    def __init__(self, hidden_dim, buffer_size, gamma, device):
        self.env = make("connectx")
        self.device = device
        self.policy = Net(self.env.configuration.columns * self.env.configuration.rows, hidden_dim, self.env.configuration.columns).to(
            device)
        self.target = Net(self.env.configuration.columns * self.env.configuration.rows, hidden_dim, self.env.configuration.columns).to(
            device)
        self.target.load_state_dict(self.policy.state_dict())
        self.target.eval()
        self.buffer = ExperienceReplay(buffer_size)
        self.trainingPair = self.env.train([None, "random"])
        self.loss_function = nn.MSELoss()
        self.optimizer = optim.Adam(params=self.policy.parameters(), lr=0.01)
        self.gamma = gamma

    def change_reward(self, reward, done, board):
        if done and reward is 1:
            return 10
        if done and reward is -1:
            return -10
        if done:
            return 1
        if reward is None:
            return -20
        if reward is 0:
            return 1 / 42
        else:
            return reward

    def takeAction(self, actionList: torch.tensor, board, epsilon, train=True):
        if (np.random.random() < epsilon) & train:
            # invalide actions rein=geht nicht
            # return torch.tensor(np.random.choice(len(actionList))).item()
            return np.random.choice([i for i in range(len(actionList)) if board[0][0][0][i] == 1])
        else:
            for i in range(7):
                if board[0][0][0][i] == 0:
                    actionList[i] = float('-inf')
            return torch.argmax(actionList).item()

    def reshape(self, board: torch.tensor, unsqz=True):
        tensor = board.view(-1, 7).long()
        # [0] = wo kann er reinwerfen(da wo es geht, steht eine 1), [1] = player1 (da wo es geht steht eine 0), [2] = player2 (da wo es geht steht eine 0)
        a = F.one_hot(tensor, 3).permute([2, 0, 1])
        b = a[:, :, :]
        if unsqz:
            return torch.unsqueeze(b, 0).float().to(self.device)
        return b.float().to(self.device)

    def preprocessState(self, state):
        state = self.reshape(state, False)
        # state = torch.stack(state)
        return state

    def trainActionFromPolicy(self, state, action):
        state = self.preprocessState(state)
        value = self.policy(state)
        return value[action]

    def trainActionFromTarget(self, next_state, reward, done):
        next_state = self.preprocessState(next_state)
        target = self.target(next_state)
        target = torch.max(target, 1)[0].item()
        target = reward + ((self.gamma * target) * (1 - done))
        return target

    def train(self, batchSize):
        if len(self.buffer) > batchSize:
            self.optimizer.zero_grad()
            states, actions, rewards, next_states, dones = self.buffer.sample(batchSize, self.device)
            loss = 0
            for i in range(batchSize):
                value = self.trainActionFromPolicy(states[i], actions[i])
                target = self.trainActionFromPolicy(next_states[i], dones[i])
                loss += self.loss_function(value, target)
            loss.backward()
            self.optimizer.step()
            return loss
