import yaml
import collections
from datetime import datetime

import instagrapi
from instagrapi import Client
import tinydb

from typing import List, Any


class MyClient(instagrapi.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_medias_from_username(self, username: str):
        user_id = self.user_id_from_username(username)
        medias = self.user_medias(user_id)
        return medias


def get_hashtags_from_text(text: str) -> List[str]:
    return list({tag.strip("#") for tag in text.split() if tag.startswith("#")})


def new_post_from_user(
    client: Client,
    username: str,
    folder: str,
    top_img_n: int = 3,
    top_tag_n: int = 20,
):
    # get all the medias
    medias = client.get_medias_from_username(username)

    # get most popular pictures by the number of like
    medias = sorted(medias, reverse=True, key=lambda x: x.like_count)
    media_pks = []
    hashtags = []
    for m in medias:
        # get media
        if m.media_type == 1:   # Photo
            media_pks.append(m.pk)
        elif m.media_type == 8 and m.resources[0].media_type == 1:  # Album
            media_pks.append(m.resources[0].pk)
        else:
            continue

        if len(media_pks) >= top_img_n:
            break

    # download the pictures
    img_fpaths = []
    for pk in media_pks:
        img_fpath = client.photo_download(pk, folder)
        img_fpaths.append(img_fpath)

    # get popular hashtags
    hashtags = []
    for m in medias:
        hashtags += get_hashtags_from_text(m.caption_text)
    top_hashtags = collections.Counter(hashtags).most_common(top_tag_n)

    # make the caption
    caption = f'Model Credit: {username}\n' + '.\n'*5 + '#' + ' #'.join([h[0] for h in top_hashtags])

    # upload the new post
    uploaded_media = client.album_upload(
        img_fpaths,
        caption=caption
    )

    return uploaded_media


def main():
    # load config
    with open('config.yaml', mode='rb') as f:
        config = yaml.safe_load(f)

    # load database
    db = tinydb.TinyDB('db.json')

    # load the account list
    with open('account_list.txt') as f:
        usernames = [l.strip() for l in f.readlines()]

    # add new users
    Account = tinydb.Query()
    for username in usernames:
        r = db.search(Account.username == username)
        if len(r) == 0:
            db.insert({
                'username': username
            })

    target_account = username

    # prepare the client module for my acccount
    client = MyClient()
    account_info = config['account']
    client.login(account_info['username'], account_info['password'])

    # get photos from a target account
    new_post_from_user(
        client,
        username=target_account,
        folder=config['resources']['image_folder']
    )

    # record the uploaded date
    now = datetime.now()
    db.update({'last_upload': str(now)}, Account.username == target_account)


if __name__ == '__main__':
    main()
