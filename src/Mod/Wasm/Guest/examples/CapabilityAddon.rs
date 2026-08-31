#![no_std]

use core::panic::PanicInfo;
use core::ptr;

mod freecad_wasm_api {
    include!(env!("FREECAD_WASM_API_RS"));
}

use freecad_wasm_api::RawClient;

#[panic_handler]
fn panic(_info: &PanicInfo<'_>) -> ! {
    loop {}
}

const FAILURE: u64 = 0x1_0000_0000;

#[no_mangle]
pub extern "C" fn freecad_addon_entry(_input: *const u8, _input_length: u32) -> u64 {
    unsafe {
        let client = RawClient::new();
        let document_name = b"RustCapabilityExample";
        let Ok(document) = client.document_new(document_name) else {
            return FAILURE;
        };

        let Ok(left) = client.vector_new(1.0, 2.0, 3.0) else {
            return FAILURE;
        };
        let Ok(right) = client.vector_new(4.0, 5.0, 6.0) else {
            return FAILURE;
        };
        let Ok(sum) = client.vector_add(left, right) else {
            return FAILURE;
        };
        let Ok(dot) = client.vector_dot(left, right) else {
            return FAILURE;
        };
        let Ok(cross) = client.vector_cross(left, right) else {
            return FAILURE;
        };
        let expected_sum = freecad_wasm_api::FreeCADBaseVectorValue {
            x: 5.0,
            y: 7.0,
            z: 9.0,
        };
        let expected_cross = freecad_wasm_api::FreeCADBaseVectorValue {
            x: -3.0,
            y: 6.0,
            z: -3.0,
        };
        if sum != expected_sum || dot != 32.0 || cross != expected_cross {
            return FAILURE;
        }

        let Ok(shape) = client.part_make_box(10.0, 20.0, 30.0) else {
            return FAILURE;
        };

        let object_name = b"RustBox";
        if client.document_open_transaction(document, b"Add object") != Ok(true) {
            return FAILURE;
        }
        let Ok(object) = client.document_add_object(document, shape, object_name) else {
            return FAILURE;
        };
        if client.document_commit_transaction(document) != Ok(true) {
            return FAILURE;
        }

        let mut label = [0u8; 128];
        let Ok(label_length) = client.document_object_get_label(object, &mut label) else {
            return FAILURE;
        };
        if &label[..label_length] != b"RustBox"
            || client.document_open_transaction(document, b"Set label") != Ok(true)
            || client.document_object_set_label(object, b"ConfiguredBox") != Ok(())
            || client.document_commit_transaction(document) != Ok(true)
            || client.document_open_transaction(document, b"Rollback label") != Ok(true)
            || client.document_object_set_label(object, b"TemporaryBox") != Ok(())
            || client.document_abort_transaction(document) != Ok(true)
        {
            return FAILURE;
        }
        let Ok(label_length) = client.document_object_get_label(object, &mut label) else {
            return FAILURE;
        };
        if &label[..label_length] != b"ConfiguredBox" {
            return FAILURE;
        }

        let Ok(saved) = client.document_is_saved(document) else {
            return FAILURE;
        };
        if saved {
            return FAILURE;
        }

        let Ok(queried_object) = client.document_get_object(document, object_name) else {
            return FAILURE;
        };
        let Ok(is_null) = client.topo_shape_is_null(shape) else {
            return FAILURE;
        };
        let Ok(is_valid) = client.topo_shape_is_valid(shape) else {
            return FAILURE;
        };
        let Ok(length) = client.topo_shape_length(shape) else {
            return FAILURE;
        };
        let Ok(area) = client.topo_shape_area(shape) else {
            return FAILURE;
        };
        let Ok(volume) = client.topo_shape_volume(shape) else {
            return FAILURE;
        };
        if is_null || !is_valid || length != 480.0 || area != 2200.0 || volume != 6000.0 {
            return FAILURE;
        }

        if client.release(queried_object.0).is_err()
            || client.release(object.0).is_err()
            || client.release(shape.0).is_err()
            || client.release(document.0).is_err()
        {
            return FAILURE;
        }

        let response_address = client.allocate_response(2);
        if response_address == 0 {
            return FAILURE;
        }
        ptr::write(response_address as *mut u8, b'O');
        ptr::write((response_address + 1) as *mut u8, b'K');
        (2u64 << 32) | response_address as u64
    }
}
