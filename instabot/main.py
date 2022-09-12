import sys
import yaml
import time
import random
import collections
from datetime import datetime, timedelta

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


def main():
    CONFIG_PATH = 'config.yaml'
    ACCOUNT_LIST_PATH = 'account_list.txt'

    top_media_n = 3
    top_tag_n = 30

    # load config
    with open(CONFIG_PATH, mode='rb') as f:
        config = yaml.safe_load(f)

    # load database
    DB_PATH = config['account']['db']
    db = tinydb.TinyDB(DB_PATH)

    # add new users from the account list
    Account = tinydb.Query()
    with open(ACCOUNT_LIST_PATH, mode='r+', encoding='UTF-8') as f:
        usernames = [l.strip() for l in f.readlines()]
        # add users
        for username in usernames:
            db.upsert({'username': username}, Account.username == username)
        # remove every lines
        f.seek(0)
        f.truncate()

    # get target users
    today = datetime.now()
    target_users = db.search(
        (~ Account.last_upload.exists()) \
        | (today - timedelta(days=60) > Account.last_upload.map(datetime.fromisoformat))
    )
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
            print(f'ERROR: could not get any media from @{target_username}')
            continue

        # get most popular pictures by the number of like
        medias = sorted(medias, reverse=True, key=lambda x: x.like_count)
        top_medias = []
        hashtags = []
        for m in medias:
            # get media
            if m.media_type == 1:   # Photo
                tmp_medias = [m]
            elif m.media_type == 2: # Video
                # download the video
                media_fpath = client.clip_download(m.pk, folder)
                # upload reels
                uploaded_media = client.clip_upload(
                    path=media_fpath,
                    caption=m.caption_text,
                )
                print(f'Success to upload the reel from @{target_username} !!!')
                # update the db
                db.update(
                    {
                        'last_upload': str(datetime.now()),
                        'used_media_pks': m.pk,
                    },
                    Account.username == target_username
                )
                time.sleep(500)
            elif m.media_type == 8:  # Album
                tmp_medias = m.resources
            else:
                continue

            # check the duplication
            target_account = db.search(Account.username == target_username)[0]
            for _m in tmp_medias:
                if ('used_media_pks' not in target_account.keys()) or (_m.pk not in target_account.used_media_pks):
                    top_medias.append(_m)
                    hashtags += get_hashtags_from_text(m.caption_text)

            if len(top_medias) >= top_media_n:
                break

        # get popular hashtags
        top_hashtags = collections.Counter(hashtags).most_common(top_tag_n)
        top_hashtags = [h[0] for h in top_hashtags]
        if len(top_hashtags) < top_tag_n:
            top_hashtags += random.sample(config['templates']['hashtags'], top_tag_n - len(top_hashtags))

        # download the pictures
        media_pks = []
        media_fpaths = []
        folder = config['resources']['image_folder']
        for m in top_medias:
            if m.media_type == 1:   # Photo
                media_fpath = client.photo_download(m.pk, folder)
                if media_fpath.suffix != '.jpg':
                    media_fpath = media_fpath.rename(media_fpath.with_suffix('.jpg'))
            elif m.media_type == 2 and m.product_type == 'feed':
                media_fpath = client.video_download(m.pk, folder)
            elif m.media_type == 2 and m.product_type == 'igtv':
                media_fpath = client.igtv_download(m.pk, folder)
            elif m.media_type == 2 and m.product_type == 'clips':
                media_fpath = client.clip_download(m.pk, folder)
            else:
                continue
            media_pks.append(m.pk)
            media_fpaths.append(media_fpath)

        # make the caption
        caption = 'Which one do you like most??  どの写真が好きですか？\n' if len(media_fpaths) > 1 else ''
        caption += f'Follow us with beautiful model: {target_username}\n'
        caption += '.\n'*5 + '#' + ' #'.join(top_hashtags)

        # upload the new post
        uploaded_media = client.album_upload(
            media_fpaths,
            caption=caption
        )
        print(f'Success to upload the content from {target_username} !!!')

        # handle exceptions
        if uploaded_media.caption_text == '':
            print('Error: Failed upload (empty caption)')
            sys.exit(1)

        # record the uploaded date
        target_account = db.search(Account.username == target_username)[0]
        media_pks = list(set(media_pks + target_account.get('used_media_pks', [])))
        hashtags = list(set(hashtags + target_account.get('used_hashtags', [])))
        db.update(
            {
                'last_upload': str(datetime.now()),
                'used_media_pks': media_pks,
                'used_hashtags': hashtags,
            },
            Account.username == target_username
        )

        time.sleep(3600 * 4)


if __name__ == '__main__':
    main()
