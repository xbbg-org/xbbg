use xbbg_core::CorrelationId;

use super::SlabKey;

/// High-bit tag for CorrelationIds generated for async `open_service` calls.
/// Dispatch CIDs never set this bit, keeping the two ID spaces disjoint.
pub(super) const SERVICE_OPEN_CID_TAG: i64 = 1_i64 << 62;

const SLOT_BITS: u32 = 32;
const SLOT_MASK: i64 = (1_i64 << SLOT_BITS) - 1;
const GENERATION_MASK: i64 = (1_i64 << 30) - 1;

/// Internal dispatch token encoded into Bloomberg integer correlation IDs.
///
/// Layout (always positive, bit 62 reserved for service-open CIDs):
/// - bits 0..32: slab key + 1, so Bloomberg never sees `Int(0)` from the
///   async engine's explicit request/subscription dispatch path
/// - bits 32..62: optional generation tag (0 = untagged; subscriptions)
///
/// The generation makes request correlation IDs single-use even when slab
/// slots are recycled. Bloomberg guarantees no further messages for a
/// cancelled CID once `cancel()` returns (blpapi_abstractsession.h), but that
/// guarantee is void when `cancel()` itself fails; a late message would then
/// decode to a recycled slot index. The generation comparison at dispatch
/// drops such stale messages instead of misrouting them into the slot's new
/// occupant, at the cost of one integer compare.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(super) struct DispatchKey(i64);

impl DispatchKey {
    /// Encode an untagged dispatch key (generation 0).
    ///
    /// Used by the subscription pool, where correlation IDs must stay stable
    /// for the life of the subscription (unsubscribe matches by CID value)
    /// and slot-recycling races are handled by `pending_cancel` tombstones.
    pub(super) fn from_slab_key(slab_key: SlabKey) -> Self {
        Self::with_generation(slab_key, 0)
    }

    /// Encode a dispatch key carrying a 30-bit generation tag.
    pub(super) fn with_generation(slab_key: SlabKey, generation: u32) -> Self {
        let slot = u32::try_from(slab_key)
            .ok()
            .and_then(|key| key.checked_add(1))
            .expect("slab key exceeds Bloomberg integer correlation range");
        let value = ((i64::from(generation) & GENERATION_MASK) << SLOT_BITS) | i64::from(slot);
        Self(value)
    }

    pub(super) fn from_correlation_id(correlation_id: &CorrelationId) -> Option<Self> {
        match correlation_id {
            CorrelationId::Int(value)
                if *value > 0
                    && (*value & SERVICE_OPEN_CID_TAG) == 0
                    && (*value & SLOT_MASK) != 0 =>
            {
                Some(Self(*value))
            }
            _ => None,
        }
    }

    pub(super) fn to_slab_key(self) -> SlabKey {
        usize::try_from((self.0 & SLOT_MASK) - 1)
            .expect("dispatch key does not fit the current platform slab range")
    }

    /// Generation tag carried by this key (0 when untagged).
    pub(super) fn generation(self) -> u32 {
        ((self.0 >> SLOT_BITS) & GENERATION_MASK) as u32
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
            assert_eq!(decoded.generation(), 0);
        }
    }

    #[test]
    fn dispatch_key_round_trips_generations() {
        for (slab_key, generation) in [(0usize, 1u32), (7, 42), (1024, (1 << 30) - 1)] {
            let dispatch_key = DispatchKey::with_generation(slab_key, generation);
            let correlation_id = dispatch_key.to_correlation_id();
            let decoded = DispatchKey::from_correlation_id(&correlation_id)
                .expect("dispatch key should decode from correlation id");

            assert_eq!(decoded.to_slab_key(), slab_key);
            assert_eq!(decoded.generation(), generation);
            assert_eq!(decoded, dispatch_key);
        }
    }

    #[test]
    fn dispatch_key_generation_wraps_into_mask() {
        // Generations above 30 bits fold into the mask without touching the
        // service tag bit or the sign bit.
        let dispatch_key = DispatchKey::with_generation(3, u32::MAX);
        let cid = dispatch_key.to_correlation_id();
        let CorrelationId::Int(raw) = cid else {
            panic!("expected integer correlation id");
        };
        assert!(raw > 0);
        assert_eq!(raw & SERVICE_OPEN_CID_TAG, 0);
        assert_eq!(dispatch_key.to_slab_key(), 3);
        assert_eq!(dispatch_key.generation(), (1 << 30) - 1);
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
        // Service-open CIDs (bit 62) and values with an empty slot field must
        // never decode into slab keys.
        assert!(
            DispatchKey::from_correlation_id(&CorrelationId::Int(SERVICE_OPEN_CID_TAG | 5))
                .is_none()
        );
        assert!(DispatchKey::from_correlation_id(&CorrelationId::Int(1_i64 << 32)).is_none());
        // SAFETY: the null pointer is never dereferenced; this only verifies
        // dispatch rejects non-integer correlation IDs.
        let ptr_cid = unsafe { CorrelationId::new_ptr(std::ptr::null_mut()) };
        assert!(DispatchKey::from_correlation_id(&ptr_cid).is_none());
    }
}
