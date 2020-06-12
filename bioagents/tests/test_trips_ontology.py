from bioagents.resources.trips_ont_manager import trips_isa


def test_isa_disease():
    assert trips_isa('diabetes', 'disease')
    assert not trips_isa('disease', 'diabetes')
    assert trips_isa('cancer', 'medical-disorders-and-conditions')
    assert trips_isa('ONT::CANCER', 'disease')
    assert trips_isa('ont::cancer', 'disease')
    assert trips_isa('CANCER', 'ONT::DISEASE')


def test_isa_disease_equal():
    assert trips_isa('cancer', 'cancer')
