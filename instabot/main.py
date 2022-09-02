import yaml
import collections

import instagrapi
from instagrapi import Client
import tinydb
from tinydb import TinyDB, Query

from typing import List


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
    user_id = client.user_id_from_username(username)
    medias = client.user_medias(user_id)

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
    caption = f'Model Credit: {username}' + '.\n'*7 + '#' + ' #'.join([h[0] for h in top_hashtags])

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
    db = TinyDB('db.json')

    # prepare the client module for my acccount
    client = Client()
    account_info = config['account']
    client.login(account_info['username'], account_info['password'])

    # get photos from a target account
    new_post_from_user(
        client,
        username='',
        folder=config['resources']['image_folder']
    )


if __name__ == '__main__':
    main()
