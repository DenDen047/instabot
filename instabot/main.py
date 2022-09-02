import yaml
from instagrapi import Client

from typing import List


def get_photos(
    client: Client,
    username: str,
    folder: str,
    top_n: int = 3
) -> List[str]:
    # get all the medias
    user_id = client.user_id_from_username(username)
    medias = client.user_medias(user_id)

    # get most popular pictures by the number of like
    medias = sorted(medias, reverse=True, key=lambda x: x.like_count)
    media_pks = []
    for m in medias:
        if m.media_type == 1:   # Photo
            media_pks.append(m.pk)
        elif m.media_type == 8 and m.resources[0].media_type == 1:  # Album
            media_pks.append(m.resources[0].pk)
        else:
            continue

        if len(media_pks) >= top_n:
            break

    # download the pictures
    img_fpaths = []
    for pk in media_pks:
        img_fpath = client.photo_download(pk, folder)
        img_fpaths.append(img_fpath)

    return img_fpaths


def main():
    # load config
    with open('config.yaml', mode='rb') as f:
        config = yaml.safe_load(f)

    # prepare the client module for my acccount
    client = Client()
    account_info = config['account']
    client.login(account_info['username'], account_info['password'])

    # get photos from a target account
    img_fpaths = get_photos(
        client,
        username='amypanaretou',
        folder=config['resources']['image_folder']
    )
    print(img_fpaths)


if __name__ == '__main__':
    main()
