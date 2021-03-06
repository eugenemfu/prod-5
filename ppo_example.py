import os
import sys
import shutil
from gym import spaces

import ray
import ray.rllib.agents.ppo as ppo
from ray import tune
from PIL import Image

import wandb
wandb.init(project="prod-5", entity="eugene_mfu")

sys.path.append(os.path.abspath("mapgen"))
os.environ["PYTHONPATH"] = os.path.abspath("mapgen")
from mapgen import Dungeon


TOTAL_EXPLORED_FACTOR = 0.02
IS_NOT_NEW_FINE = 1
IS_NOT_MOVED_FINE = 5


class ModifiedDungeon(Dungeon):
    """Use this class to change the behavior of the original env (e.g. remove the trajectory from observation, like here)"""
    def __init__(self,
        width=20,
        height=20,
        max_rooms=3,
        min_room_xy=5,
        max_room_xy=12,
        max_steps: int = 400
    ):
        observation_size = 11
        super().__init__(
            width=width,
            height=height,
            max_rooms=max_rooms,
            min_room_xy=min_room_xy,
            max_room_xy=max_room_xy,
            observation_size=11,
            vision_radius=5,
            max_steps=max_steps
        )

        self.observation_space = spaces.Box(0, 1, [observation_size, observation_size, 3])  # because we remove trajectory and leave only cell types (UNK, FREE, OCCUPIED)
        self.action_space = spaces.Discrete(3)
        self.seed(42)

    def step(self, action):
        observation, reward, done, info = super().step(action)
        observation = observation[:, :, :-1]  # remove trajectory
        reward *= 1 + info['total_explored'] * TOTAL_EXPLORED_FACTOR
        if not info['is_new']:
            reward -= IS_NOT_NEW_FINE
        if not info['moved']:
            reward -= IS_NOT_MOVED_FINE

        return observation, reward, done, info

    def reset(self):
        observation = super().reset()
        observation = observation[:, :, :-1]  # remove trajectory
        return observation
    

if __name__ == "__main__":

    ray.shutdown()
    ray.init(ignore_reinit_error=True)
    tune.register_env("ModifiedDungeon", lambda config: ModifiedDungeon(**config))


    CHECKPOINT_ROOT = "tmp/ppo/dungeon"
    shutil.rmtree(CHECKPOINT_ROOT, ignore_errors=True, onerror=None)

    ray_results = os.getenv("HOME") + "/ray_results1/"
    shutil.rmtree(ray_results, ignore_errors=True, onerror=None)

    config = ppo.DEFAULT_CONFIG.copy()
    config["num_gpus"] = 0
    config["log_level"] = "INFO"
    config["framework"] = "torch"
    config["env"] = "ModifiedDungeon"
    config["env_config"] = {
        "width": 20,
        "height": 20,
        "max_rooms": 3,
        "min_room_xy": 5,
        "max_room_xy": 10,
       # "observation_size": 11,
       # "vision_radius": 5
    }

    config["model"] = {
        "conv_filters": [
            [16, (3, 3), 2],
            [32, (3, 3), 2],
            [32, (3, 3), 1],
        ],
        "post_fcnet_hiddens": [32],
        "post_fcnet_activation": "relu",
        "vf_share_layers": False,
    }


    config["rollout_fragment_length"] = 100
    config["entropy_coeff"] = 0.1
    config["lambda"] = 0.95
    config["vf_loss_coeff"] = 1.0



    agent = ppo.PPOTrainer(config)


    N_ITER = 300
    s = "{:3d} reward {:6.2f}/{:6.2f}/{:6.2f} len {:6.2f} saved {}"

    #env = Dungeon(50, 50, 3)

    wandb.config = {}
    wandb.config["rollout_fragment_length"] = config["rollout_fragment_length"]
    wandb.config["entropy_coeff"] = config["entropy_coeff"]
    wandb.config["lambda"] = config["lambda"]
    wandb.config["vf_loss_coeff"] = config["vf_loss_coeff"]
    wandb.config["iterations"] = N_ITER
    wandb.config["TOTAL_EXPLORED_FACTOR"] = TOTAL_EXPLORED_FACTOR
    wandb.config["IS_NOT_NEW_FINE"] = IS_NOT_NEW_FINE
    wandb.config["IS_NOT_MOVED_FINE"] = IS_NOT_MOVED_FINE


    for n in range(N_ITER):
        result = agent.train()
        #print(result.keys())
        file_name = agent.save(CHECKPOINT_ROOT)

        print(s.format(
            n + 1,
            result["episode_reward_min"],
            result["episode_reward_mean"],
            result["episode_reward_max"],
            result["episode_len_mean"],
            file_name
        ))

        # sample trajectory
        env = ModifiedDungeon(20, 20, 3, min_room_xy=5, max_room_xy=10)
        obs = env.reset()
        Image.fromarray(env._map.render(env._agent)).convert('RGB').resize((500, 500), Image.NEAREST).save('tmp.png')

        frames = []

        for _ in range(500):
            action = agent.compute_single_action(obs)

            frame = Image.fromarray(env._map.render(env._agent)).convert('RGB').resize((500, 500), Image.NEAREST).quantize()
            frames.append(frame)

            #frame.save('tmp1.png')
            obs, reward, done, info = env.step(action)
            if done:
                break

        frames[0].save(f"out.gif", save_all=True, append_images=frames[1:], loop=0, duration=1000/60)

        wandb.log({
            "episode_reward_min": result["episode_reward_min"],
            "episode_reward_mean": result["episode_reward_mean"],
            "episode_reward_max": result["episode_reward_max"],
            "episode_len_mean": result["episode_len_mean"],
            "gif": wandb.Video("out.gif")
        })
        
