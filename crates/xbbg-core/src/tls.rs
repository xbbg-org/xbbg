use std::ffi::CString;

use crate::errors::{BlpError, Result};
use crate::ffi;

pub struct TlsOptions {
    ptr: *mut ffi::blpapi_TlsOptions_t,
}

unsafe impl Send for TlsOptions {}
unsafe impl Sync for TlsOptions {}

impl TlsOptions {
    pub fn from_files(
        client_credentials_path: &str,
        client_credentials_password: &str,
        trust_material_path: &str,
    ) -> Result<Self> {
        let creds = cstring(client_credentials_path, "client credentials path")?;
        let password = cstring(client_credentials_password, "client credentials password")?;
        let trust = cstring(trust_material_path, "trust material path")?;

        let ptr = unsafe {
            ffi::blpapi_TlsOptions_createFromFiles(
                creds.as_ptr(),
                password.as_ptr(),
                trust.as_ptr(),
            )
        };

        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "failed to create TlsOptions from files".into(),
            });
        }

        Ok(Self { ptr })
    }

    pub fn from_blobs(
        client_credentials: &[u8],
        client_credentials_password: &str,
        trust_material: &[u8],
    ) -> Result<Self> {
        let password = cstring(client_credentials_password, "client credentials password")?;

        let ptr = unsafe {
            ffi::blpapi_TlsOptions_createFromBlobs(
                client_credentials.as_ptr() as *const i8,
                client_credentials.len() as i32,
                password.as_ptr(),
                trust_material.as_ptr() as *const i8,
                trust_material.len() as i32,
            )
        };

        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "failed to create TlsOptions from blobs".into(),
            });
        }

        Ok(Self { ptr })
    }

    pub fn set_tls_handshake_timeout_ms(&mut self, timeout_ms: i32) {
        unsafe { ffi::blpapi_TlsOptions_setTlsHandshakeTimeoutMs(self.ptr, timeout_ms) };
    }

    pub fn set_crl_fetch_timeout_ms(&mut self, timeout_ms: i32) {
        unsafe { ffi::blpapi_TlsOptions_setCrlFetchTimeoutMs(self.ptr, timeout_ms) };
    }

    pub(crate) fn as_ptr(&self) -> *const ffi::blpapi_TlsOptions_t {
        self.ptr
    }
}

impl Drop for TlsOptions {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            unsafe { ffi::blpapi_TlsOptions_destroy(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}

fn cstring(value: &str, field: &str) -> Result<CString> {
    CString::new(value).map_err(|e| BlpError::InvalidArgument {
        detail: format!("invalid {field}: {e}"),
    })
}
