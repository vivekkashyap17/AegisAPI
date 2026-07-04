from app.services.features import extract_features, NUM_FEATURES


def test_vector_length(make_event):
    assert len(extract_features(make_event())) == NUM_FEATURES == 7


def test_normal_get_vector(make_event):
    f = extract_features(make_event(response_time=45, status_code=200, payload_size=200,
                                    method="GET", endpoint="/items"))
    # [response_time, status_code, payload_size, is_sensitive, is_error, method_code, endpoint_len]
    assert f == [45.0, 200.0, 200.0, 0.0, 0.0, 0.0, 6.0]


def test_sensitive_error_delete_vector(make_event):
    f = extract_features(make_event(endpoint="/admin", status_code=500, method="DELETE"))
    assert f[3] == 1.0   # is_sensitive_endpoint
    assert f[4] == 1.0   # is_error
    assert f[5] == 3.0   # DELETE
    assert f[6] == 6.0   # len("/admin")


def test_method_encoding(make_event):
    assert extract_features(make_event(method="GET"))[5] == 0.0
    assert extract_features(make_event(method="POST"))[5] == 1.0
    assert extract_features(make_event(method="PUT"))[5] == 2.0
    assert extract_features(make_event(method="DELETE"))[5] == 3.0


def test_unknown_method_maps_to_4(make_event):
    assert extract_features(make_event(method="PATCH"))[5] == 4.0


def test_method_is_case_insensitive(make_event):
    assert extract_features(make_event(method="post"))[5] == 1.0


def test_error_flag_boundary_400(make_event):
    assert extract_features(make_event(status_code=400))[4] == 1.0
    assert extract_features(make_event(status_code=399))[4] == 0.0


def test_payload_size_none_defaults_to_zero(make_event):
    assert extract_features(make_event(payload_size=None))[2] == 0.0
