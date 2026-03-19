use xbbg_core::CorrelationId;

use super::SlabKey;

/// Internal dispatch token encoded into Bloomberg integer correlation IDs.
///
/// Slab keys are offset by +1 so Bloomberg never sees `Int(0)` from the
/// async engine's explicit request/subscription dispatch path.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(super) struct DispatchKey(i64);

impl DispatchKey {
    pub(super) fn from_slab_key(slab_key: SlabKey) -> Self {
        let value = i64::try_from(slab_key)
            .expect("slab key exceeds Bloomberg integer correlation range")
            .checked_add(1)
            .expect("dispatch key overflowed Bloomberg integer correlation range");
        Self(value)
    }

    pub(super) fn from_correlation_id(correlation_id: &CorrelationId) -> Option<Self> {
        match correlation_id {
            CorrelationId::Int(value) if *value > 0 => Some(Self(*value)),
            _ => None,
        }
    }

    pub(super) fn to_slab_key(self) -> SlabKey {
        usize::try_from(self.0 - 1)
            .expect("dispatch key does not fit the current platform slab range")
    }

    pub(super) fn to_correlation_id(self) -> CorrelationId {
        CorrelationId::Int(self.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dispatch_key_round_trips_slab_keys() {
        for slab_key in [0usize, 1, 7, 1024] {
            let dispatch_key = DispatchKey::from_slab_key(slab_key);
            let correlation_id = dispatch_key.to_correlation_id();
            let decoded = DispatchKey::from_correlation_id(&correlation_id)
                .expect("dispatch key should decode from correlation id");

            assert_eq!(decoded.to_slab_key(), slab_key);
        }
    }

    #[test]
    fn dispatch_key_never_produces_zero_correlation_id() {
        let dispatch_key = DispatchKey::from_slab_key(0);

        assert_eq!(dispatch_key.to_correlation_id(), CorrelationId::Int(1));
    }

    #[test]
    fn dispatch_key_rejects_non_dispatch_correlation_ids() {
        assert!(DispatchKey::from_correlation_id(&CorrelationId::Unset).is_none());
        assert!(DispatchKey::from_correlation_id(&CorrelationId::Int(0)).is_none());
        assert!(DispatchKey::from_correlation_id(&CorrelationId::Int(-1)).is_none());
        assert!(
            DispatchKey::from_correlation_id(&CorrelationId::Ptr(std::ptr::null_mut())).is_none()
        );
    }
}
