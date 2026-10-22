import main


def test_main_prints_greeting(capsys):
    main.main()
    assert capsys.readouterr().out == "Hello from trans-sub!\n"
