#![no_std]

use core::panic::PanicInfo;
use core::ptr;

#[panic_handler]
fn panic(_info: &PanicInfo<'_>) -> ! {
    loop {}
}

#[link(wasm_import_module = "freecad")]
unsafe extern "C" {
    fn freecad_alloc(size: u32) -> u32;
    fn freecad_dispatch(request: *const u8, request_length: u32) -> u64;
    fn freecad_release(response_address: u32);
}

const FAILURE: u64 = 0x1_0000_0000;
const REQUEST_CAPACITY: usize = 128;

static mut REQUEST: [u8; REQUEST_CAPACITY] = [0; REQUEST_CAPACITY];

unsafe fn request_header(operation: u8, payload_length: u32) -> usize {
    let header = [
        b'F',
        b'C',
        b'W',
        b'A',
        1,
        operation,
        0,
        0,
        payload_length as u8,
        (payload_length >> 8) as u8,
        (payload_length >> 16) as u8,
        (payload_length >> 24) as u8,
    ];
    let request = ptr::addr_of_mut!(REQUEST).cast::<u8>();
    ptr::copy_nonoverlapping(header.as_ptr(), request, header.len());
    header.len()
}

unsafe fn append_bytes(offset: &mut usize, bytes: &[u8]) {
    let request = ptr::addr_of_mut!(REQUEST).cast::<u8>().add(*offset);
    ptr::copy_nonoverlapping(bytes.as_ptr(), request, bytes.len());
    *offset += bytes.len();
}

unsafe fn append_u32(offset: &mut usize, value: u32) {
    append_bytes(offset, &value.to_le_bytes());
}

unsafe fn append_u64(offset: &mut usize, value: u64) {
    append_bytes(offset, &value.to_le_bytes());
}

unsafe fn dispatch_handle(request_length: usize) -> Option<u64> {
    let request = ptr::addr_of!(REQUEST).cast::<u8>();
    let response = freecad_dispatch(request, request_length as u32);
    let address = response as u32;
    let length = (response >> 32) as u32;
    if address == 0 || length != 8 {
        if address != 0 {
            freecad_release(address);
        }
        return None;
    }

    let mut bytes = [0u8; 8];
    ptr::copy_nonoverlapping(address as *const u8, bytes.as_mut_ptr(), bytes.len());
    freecad_release(address);
    Some(u64::from_le_bytes(bytes))
}

unsafe fn dispatch_release(handle: u64) -> bool {
    let mut offset = request_header(4, 8);
    append_u64(&mut offset, handle);
    let request = ptr::addr_of!(REQUEST).cast::<u8>();
    let response = freecad_dispatch(request, offset as u32);
    let address = response as u32;
    let length = (response >> 32) as u32;
    if address != 0 {
        freecad_release(address);
    }
    length == 0
}

#[no_mangle]
pub extern "C" fn freecad_addon_entry(_input: *const u8, _input_length: u32) -> u64 {
    unsafe {
        let document_name = b"RustCapabilityExample";
        let mut offset = request_header(1, 4 + document_name.len() as u32);
        append_u32(&mut offset, document_name.len() as u32);
        append_bytes(&mut offset, document_name);
        let Some(document) = dispatch_handle(offset) else {
            return FAILURE;
        };

        let mut offset = request_header(2, 24);
        append_u64(&mut offset, 10.0f64.to_bits());
        append_u64(&mut offset, 20.0f64.to_bits());
        append_u64(&mut offset, 30.0f64.to_bits());
        let Some(shape) = dispatch_handle(offset) else {
            return FAILURE;
        };

        let object_name = b"RustBox";
        let mut offset = request_header(3, 20 + object_name.len() as u32);
        append_u64(&mut offset, document);
        append_u64(&mut offset, shape);
        append_u32(&mut offset, object_name.len() as u32);
        append_bytes(&mut offset, object_name);
        if dispatch_handle(offset).is_none() {
            return FAILURE;
        }

        if !dispatch_release(shape) {
            return FAILURE;
        }

        let response_address = freecad_alloc(2);
        if response_address == 0 {
            return FAILURE;
        }
        ptr::write(response_address as *mut u8, b'O');
        ptr::write((response_address + 1) as *mut u8, b'K');
        (2u64 << 32) | response_address as u64
    }
}
