from streamlit.testing.v1 import AppTest


def test_home_page_and_merge_navigation() -> None:
    app = AppTest.from_file("app.py").run(timeout=10)

    assert not app.exception
    assert [title.value for title in app.title] == ["本機 PDF 工具箱"]
    assert app.button[0].label == "開啟合併工具"
    assert app.button[1].label == "尚未開放"
    assert app.button[1].disabled

    app.button[0].click().run(timeout=10)

    assert not app.exception
    assert [title.value for title in app.title] == ["合併 PDF"]
    assert app.button[0].label == "合併 PDF"
    assert app.button[0].disabled
