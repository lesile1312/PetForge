from importlib import import_module

import pytest


def _api():
    try:
        return import_module("petforge_worker.providers.base")
    except ModuleNotFoundError:
        pytest.fail("photo provider contracts are not implemented")


def _person(api, box=(0.2, 0.1, 0.4, 0.8), confidence=0.9):
    return api.PersonCandidate(bbox_xywh_norm=box, landmarks_norm={}, confidence=confidence)


def test_single_person_is_selected_without_prompt():
    api = _api()
    person = _person(api)

    selected = api.resolve_person_selection([person], image_size=(1000, 800))

    assert selected == person


def test_group_photo_requires_explicit_person_index():
    api = _api()
    people = [_person(api), _person(api, box=(0.6, 0.1, 0.3, 0.8))]

    with pytest.raises(api.PersonSelectionError, match="person_selection_required"):
        api.resolve_person_selection(people, image_size=(1000, 800))

    assert api.resolve_person_selection(people, index=1, image_size=(1000, 800)) == people[1]


def test_manual_crop_fallback_maps_pixels_to_normalized_source_box():
    api = _api()

    selected = api.resolve_person_selection(
        [],
        crop_xywh_px=(100, 50, 400, 700),
        image_size=(1000, 1000),
    )

    assert selected.bbox_xywh_norm == pytest.approx((0.1, 0.05, 0.4, 0.7))
    assert selected.confidence == 0
    assert selected.landmarks_norm == {}


@pytest.mark.parametrize(
    "crop",
    [(0, 0, 0, 2), (-1, 0, 2, 2), (9, 9, 2, 2), (1.5, 2, 3, 4)],
)
def test_manual_crop_rejects_invalid_bounds(crop):
    api = _api()
    with pytest.raises(api.PersonSelectionError, match="invalid_manual_crop"):
        api.resolve_person_selection([], crop_xywh_px=crop, image_size=(10, 10))


def test_cancel_token_is_cooperative_and_raises_stable_error():
    api = _api()
    cancel = api.CancelToken()
    cancel.cancel()
    with pytest.raises(api.GenerationCancelled, match="generation_cancelled"):
        cancel.check()
