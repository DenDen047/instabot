import yaml
from instagrapi import Client


if __name__ == '__main__':
    # load config
    with open('config.yaml', mode='rb') as f:
        config = yaml.safe_load(f)

    # prepare the client module for my acccount
    cl = Client()
    account_info = config['account']
    cl.login(account_info['username'], account_info['password'])

    user_id = cl.user_id_from_username("emily_ratajkowski_official")
    medias = cl.user_medias(user_id, 20)
