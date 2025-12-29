use std::collections::HashMap;
use std::ffi::CString;
use std::sync::{Arc, RwLock};

use once_cell::sync::Lazy;

type PtrKey = usize;

pub struct TagRegistry {
    map: RwLock<HashMap<PtrKey, Arc<CString>>>,
}

impl TagRegistry {
    pub fn new() -> Self {
        Self {
            map: RwLock::new(HashMap::new()),
        }
    }

    pub fn register(&self, s: &str) -> (*const core::ffi::c_void, Arc<CString>) {
        let c = Arc::new(CString::new(s).expect("CString"));
        let ptr = c.as_ptr() as *const core::ffi::c_void;
        let key = ptr as usize;
        let mut w = self.map.write().unwrap();
        w.insert(key, Arc::clone(&c));
        (ptr, c)
    }

    pub fn lookup(&self, ptr: *const core::ffi::c_void) -> Option<Arc<CString>> {
        let key = ptr as usize;
        let r = self.map.read().unwrap();
        r.get(&key).cloned()
    }

    #[allow(dead_code)]
    pub fn remove(&self, ptr: *const core::ffi::c_void) {
        let key = ptr as usize;
        let mut w = self.map.write().unwrap();
        w.remove(&key);
    }
}

pub static TAG_REGISTRY: Lazy<TagRegistry> = Lazy::new(TagRegistry::new);
