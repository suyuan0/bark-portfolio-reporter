import requests


class BarkPushError(Exception):
    pass


def send_bark(
    device_key: str,
    title: str,
    body: str,
    icon: str | None = None,
    group: str = "收益日报",
    sound: str | None = None,
    url: str | None = None,
):
    api_url = "https://api.day.app/push"

    payload = {
        "device_key": device_key,
        "title": title,
        "body": body,
        "group": group,
    }

    if icon:
        payload["icon"] = icon

    if sound:
        payload["sound"] = sound

    if url:
        payload["url"] = url

    try:
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise BarkPushError(f"Bark 推送请求失败: {exc}") from exc

    result = response.json()

    if result.get("code") != 200:
        raise BarkPushError(f"Bark 推送失败: {result}")

    return result