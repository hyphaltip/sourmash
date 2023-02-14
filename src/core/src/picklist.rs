use getset::{CopyGetters, Getters, Setters};
use typed_builder::TypedBuilder;

#[derive(Default, TypedBuilder, CopyGetters, Getters, Setters, Clone)]
pub struct Picklist {
    #[getset(get = "pub", set = "pub")]
    #[builder(default = "".into())]
    coltype: String,

    #[getset(get = "pub", set = "pub")]
    #[builder(default = "".into())]
    pickfile: String,

    #[getset(get = "pub", set = "pub")]
    #[builder(default = "".into())]
    column_name: String,

    #[getset(get = "pub", set = "pub")]
    #[builder]
    pickstyle: PickStyle,
}

#[derive(Clone)]
#[repr(u32)]
pub enum PickStyle {
    Include = 1,
    Exclude = 2,
}

// TODO: remove with MSRV 1.62 and use derive(Default) instead
impl std::default::Default for PickStyle {
    fn default() -> Self {
        PickStyle::Include
    }
}
