import re
import sys
import yaml
import random
import time
import collections
from datetime import datetime, timedelta
from PIL import Image, ImageFilter

import instagrapi
import tinydb

from typing import List, Any


class MyClient(instagrapi.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_medias_from_username(self, username: str) -> List[instagrapi.types.Media]:
        user_id = self.user_id_from_username(username)
        medias = self.user_medias(user_id)
        return medias


def get_hashtags_from_text(text: str) -> List[str]:
    text = text.replace('#', ' #')
    return list({tag.strip("#") for tag in text.split() if tag.startswith("#")})


def content_download(
    client: instagrapi.Client,
    media,
    folder: str,
):
    if media.media_type == 1:   # Photo
        media_fpath = client.photo_download(media.pk, folder)
        if media_fpath.suffix != '.jpg':
            media_fpath = media_fpath.rename(media_fpath.with_suffix('.jpg'))
    elif media.media_type == 2 and media.product_type == 'feed':
        media_fpath = client.video_download(media.pk, folder)
    elif media.media_type == 2 and media.product_type == 'igtv':
        media_fpath = client.igtv_download(media.pk, folder)
    elif media.media_type == 2 and media.product_type == 'clips':
        media_fpath = client.clip_download(media.pk, folder)
    else:
        media_fpath = None

    return media_fpath


def crop_image(image_fpath):
    im = Image.open(image_fpath)
    width, height = im.size

    # Setting the points for cropped image
    left = 1
    top = 1
    right = width - 1
    bottom = height - 1
    im1 = im.crop((left, top, right, bottom))

    im1.save(image_fpath, 'JPEG')
    return image_fpath


def main():
    CONFIG_PATH = 'config.yaml'
    ACCOUNT_LIST_PATH = 'account_list.txt'

    # load config
    with open(CONFIG_PATH, mode='rb') as f:
        config = yaml.safe_load(f)

    top_tag_n = 30

    # load database
    db_fpath = config['account']['db']
    db = tinydb.TinyDB(db_fpath)

    # add new users from the account list
    Account = tinydb.Query()
    with open(ACCOUNT_LIST_PATH, mode='r+', encoding='UTF-8') as f:
        usernames = [l.strip() for l in f.readlines()]
        # add users
        for username in usernames:
            db.upsert(
                {
                    'username': username,
                    'type': 'model',
                },
                Account.username == username
            )
        # remove every lines
        f.seek(0)
        f.truncate()

    # get target users
    target_users = db.all()
    # today = datetime.now()
    # target_users = db.search(
    #     (~ Account.last_upload.exists()) \
    #     | (today - timedelta(days=7) > Account.last_upload.map(datetime.fromisoformat))
    # )
    random.shuffle(target_users)

    # prepare the client module for my acccount
    client = MyClient()
    account_info = config['account']
    client.login(account_info['username'], account_info['password'])

    for target_user in target_users:
        target_username = target_user['username']

        # get medias
        medias = client.get_medias_from_username(target_username)
        if len(medias) == 0:
            continue

        # get most popular pictures by the number of like
        medias = sorted(medias, reverse=True, key=lambda x: x.like_count)
        target_account = db.search(Account.username == target_username)[0]
        for media in medias:
            if not (
                (   # Photo or Album
                    media.media_type == 1 or \
                    media.media_type == 8 and media.resources[0].media_type == 1
                ) and \
                (   # no duplication
                    ('used_media_pks' not in target_account.keys()) \
                    or (media.pk not in target_account['used_media_pks'])
                )
            ):
                continue

            # get the media
            media_fpaths = []
            if media.media_type == 1:
                ms = [media]
            elif media.media_type == 8:
                ms = media.resources
            for m in ms:
                media_fpath = content_download(
                    client,
                    media=m,
                    folder=config['resources']['image_folder']
                )
                # quick image editting
                if media_fpath is not None and media_fpath.suffix == '.jpg':
                    media_fpath = crop_image(media_fpath)
                # record the media file path
                media_fpaths.append(media_fpath)

            # get model account
            match = re.search(r"Model.*@([\d\w_\.]+)", media.caption_text)
            if match is not None:
                model_account = match.group(1)
            else:
                model_account = ''

            # get hashtags
            hashtags = random.sample(config['templates']['hashtags'], 30)

            # make the caption
            caption = 'Follow @' + account_info['username'] + '\n'
            caption += '.\n' * 4
            caption += f'👤 Model: ★ @{model_account} ☆\n' + '.\n'*3 if len(model_account) > 0 else ''
            caption += '#' + ' #'.join(hashtags)

            # upload the new post
            if len(media_fpaths) == 1:
                uploaded_media = client.photo_upload(
                    media_fpaths[0],
                    caption=caption
                )
            else:
                uploaded_media = client.album_upload(
                    media_fpaths,
                    caption=caption
                )
            # handle exceptions
            if uploaded_media.caption_text == '':
                print('Error: Failed upload (empty caption)')
                sys.exit(1)

            # record the uploaded date
            media_pks = list(set([media.pk] + target_account.get('used_media_pks', [])))
            db.update(
                {
                    'last_upload': str(datetime.now()),
                    'used_media_pks': media_pks,
                },
                Account.username == target_username
            )

            break
        time.sleep(3600 * 4)


if __name__ == '__main__':
    main()
