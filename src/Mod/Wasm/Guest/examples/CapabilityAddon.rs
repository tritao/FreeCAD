#![no_std]

use core::panic::PanicInfo;
use core::ptr;

mod freecad_wasm_api {
    include!(env!("FREECAD_WASM_API_RS"));
}

use freecad_wasm_api::Client;

#[panic_handler]
fn panic(_info: &PanicInfo<'_>) -> ! {
    loop {}
}

const FAILURE: u64 = 0x1_0000_0000;

#[no_mangle]
pub extern "C" fn freecad_addon_entry(_input: *const u8, _input_length: u32) -> u64 {
    unsafe {
        let client = Client::new();
        let document_name = b"RustCapabilityExample";
        let Some(document) = client.document_new(document_name) else {
            return FAILURE;
        };

        let Some(left) = client.vector_new(1.0, 2.0, 3.0) else {
            return FAILURE;
        };
        let Some(right) = client.vector_new(4.0, 5.0, 6.0) else {
            return FAILURE;
        };
        let Some(sum) = client.vector_add(left, right) else {
            return FAILURE;
        };
        let Some(dot) = client.vector_dot(left, right) else {
            return FAILURE;
        };
        let Some(cross) = client.vector_cross(left, right) else {
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

        let Some(shape) = client.part_make_box(10.0, 20.0, 30.0) else {
            return FAILURE;
        };

        let object_name = b"RustBox";
        let Some(object) = client.document_add_object(document, shape, object_name) else {
            return FAILURE;
        };

        let Some(saved) = client.document_is_saved(document) else {
            return FAILURE;
        };
        if saved {
            return FAILURE;
        }

        let Some(queried_object) = client.document_get_object(document, object_name) else {
            return FAILURE;
        };
        let Some(is_null) = client.topo_shape_is_null(shape) else {
            return FAILURE;
        };
        let Some(is_valid) = client.topo_shape_is_valid(shape) else {
            return FAILURE;
        };
        let Some(length) = client.topo_shape_length(shape) else {
            return FAILURE;
        };
        let Some(area) = client.topo_shape_area(shape) else {
            return FAILURE;
        };
        let Some(volume) = client.topo_shape_volume(shape) else {
            return FAILURE;
        };
        if is_null || !is_valid || length != 480.0 || area != 2200.0 || volume != 6000.0 {
            return FAILURE;
        }

        if !client.release(queried_object.0)
            || !client.release(object.0)
            || !client.release(shape.0)
            || !client.release(document.0)
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
